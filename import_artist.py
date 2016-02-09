import musicbrainzngs
import sqlite3, sys, os, re, json, requests, urllib.request
import colorthief
import arrow
from unidecode import unidecode

# From http://flask.pocoo.org/snippets/5/
_punct_re = re.compile(r'[\t !:"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

album_art_base_url = 'http://coverartarchive.org/release/'

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        result.extend(unidecode(word).split())
    return delim.join(result)

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb

def detect_collision(slug_candidate, cursor, table):
    cursor.execute('select count(*) from {} where slug=?'.format(table), (slug_candidate,))
    if cursor.fetchall()[0][0] > 0:
        return True
    return False

def avoid_collison(slug_candidate, cursor, table):
    if not detect_collision(slug_candidate, cursor, table):
        return slug_candidate

    i = 1
    while True:
        if not detect_collision(slug_candidate + "-" + str(i), cursor, table):
            return slug_candidate + "-" + str(i)
        i += 1

def generate_slug(text, cursor, table):
    slug_candidate = slugify(text)
    return avoid_collison(slug_candidate, cursor, table)

def get_album_art_url(release_id):
    print("Getting album art for release " + release_id + "...")
    r = requests.get(album_art_base_url + release_id + '/')
    try:
        return r.json()['images'][0]['thumbnails']['large']
    except ValueError:
        return None

def get_palette(album_art_url):
    print("Getting palette...")
    try:
        tempname, _ = urllib.request.urlretrieve(album_art_url)
        color_thief = colorthief.ColorThief(tempname)
        palette = []
        for color in (color_thief.get_palette(3, 5)):
            palette.append(rgb_to_hex(color))
        
        os.remove(tempname)
        return palette
    #Blame the ColourTheif guy
    except (colorthief.QuantizationError, colorthief.ThisShouldntHappenError):
        return [None, None, None]

def get_releases(mbid):
    print("Querying MB for release groups...")
    result = musicbrainzngs.get_artist_by_id(mbid, includes=['release-groups']) 
    release_groups = result['artist']['release-group-list']
    releases = []
    for group in release_groups:
        print("Querying MB for release group " + group['id'] + "...")
        result = musicbrainzngs.get_release_group_by_id(group['id'], includes=['releases'])
        try: # Tries to get the oldest release of the group. If it fails, tries to get any release with a valid date
            release = min(result['release-group']['release-list'],
                          key=lambda release: arrow.get(release['date']+"-01-01").timestamp if len(release['date']) == 4 else arrow.get(release['date']).timestamp)
        except KeyError:
            for r in result['release-group']['release-list']:
                if 'date' in r:
                    release = r
                    break
            continue
        try:
            release['type'] = group['type']
        except KeyError:
            release['type'] = 'Unspecified'

        releases.append(release)
    return releases

def get_tracks(release_id):
    print("Getting tracks for release " + release_id + "...")
    result = musicbrainzngs.get_release_by_id(release_id, includes=['recordings'])
    tracks = result['release']['medium-list'][0]['track-list']
    # print(json.dumps(tracks, sort_keys=True, indent=4, separators=(',', ': ')))
    return tracks

def import_artist(artist_name):
    print("Querying MB for artist info...")
    result = musicbrainzngs.search_artists(artist=artist_name)
    artist_info = result['artist-list'][0]

    con = sqlite3.connect('sample.db')
    cursor = con.cursor()

    cursor.execute(
        "insert into artists (name, slug) values (?, ?)",
        (artist_info["name"], generate_slug(artist_info["name"], cursor, 'artists'))
    )

    artist_id = cursor.lastrowid
    releases = get_releases(artist_info['id'])

    for release in releases:
        release['album-art-url'] = get_album_art_url(release['id'])
        cursor.execute(
            "insert into releases (artist_id, title, slug, date, type, album_art_url) values (?, ?, ?, ?, ?, ?)",
            (artist_id,
             release['title'],
             generate_slug(release['title'], cursor, 'releases'),
             release['date'],
             release['type'],
             release['album-art-url'])
        )
        release['local-id'] = cursor.lastrowid

        if release['album-art-url']:
            palette = get_palette(release['album-art-url'])
        else:
            palette = [None, None, None]
        cursor.execute(
            "insert into release_colors (release_id, color1, color2, color3) values (?, ?, ?, ?)",
            (release['local-id'],
             palette[0],
             palette[1],
             palette[2])
        )

        tracks = get_tracks(release['id'])
        for track in tracks:
            try:
                length = track['recording']['length']
            except KeyError:
                length = None
            cursor.execute(
                "insert into tracks (release_id, title, slug, position, runtime) values (?, ?, ?, ?, ?)",
                (release['local-id'],
                 track['recording']['title'],
                 generate_slug(track['recording']['title'], cursor, 'tracks'),
                 int(track['position']),
                 length)
            )

    con.commit()

musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")

if __name__ == '__main__':
    import_artist(sys.argv[1])