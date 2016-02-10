import musicbrainzngs
import sqlite3, sys, os, re, json, requests, urllib.request
import colorthief
import arrow
from unidecode import unidecode
from multiprocessing import Pool
from multiprocessing.dummy import Pool as ThreadPool

def query_db(db, query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    cur = db.execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv


# From http://flask.pocoo.org/snippets/5/
_punct_re = re.compile(r'[\t !:"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

album_art_base_url = 'http://coverartarchive.org/release/'

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        result.extend(unidecode(word).split())
    return delim.join(result).lower()

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
        palette = [rgb_to_hex(color) for color in (color_thief.get_palette(3, 5))]
        
        os.remove(tempname)
        return palette
    #Blame the ColourTheif guy
    except (colorthief.QuantizationError, colorthief.ThisShouldntHappenError):
        return [None, None, None]

def get_releases(mbid, processed_release_mbids):
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
        if release['id'] in processed_release_mbids:
            print("Release " + release['id'] + " has already been processed")
            continue
        try:
            release['type'] = group['type']
        except KeyError:
            release['type'] = 'Unspecified'

        releases.append(release)
    return releases

    # print(json.dumps(tracks, sort_keys=True, indent=4, separators=(',', ': ')))

def get_release(release):
    release['album-art-url'] = get_album_art_url(release['id'])

    if release['album-art-url']:
        release['palette'] = get_palette(release['album-art-url'])
    else:
        release['palette'] = [None, None, None]
    print("Getting deets for release " + release['id'] + "...")
    result = musicbrainzngs.get_release_by_id(release['id'], includes=['recordings', 'artists'])
    release['tracks'] = result['release']['medium-list'][0]['track-list']
    release['artists'] = result['release']['artist-credit']

def import_artist(artist_name):
    print("Querying MB for artist info...")
    result = musicbrainzngs.search_artists(artist=artist_name)
    artist_info = result['artist-list'][0]

    db = sqlite3.connect("sample.db")
    cursor = db.cursor()

    # TODO: 
        # Releases may not be deterministically chosen from release groups. Do.

    # Check if the artist's MBID matches the 'incomplete' field of any other artists
    # If so, get the artist_id and set the 'incomplete' field to NULL
    # If not, import as a new artist into the database
    cursor.execute('select id from artists where incomplete=?', (artist_info['id'],))
    result = cursor.fetchall()
    try:
        (artist_id,) = result[0]
        cursor.execute('select release_id from authors where artist_id=?', (artist_id,))
        processed_release_ids = [_id for (_id,) in cursor.fetchall()]
        processed_release_mbids = [mbid for (mbid,) in [query_db(db,'select mbid from release_mbid where release_id=?', (release_id,), True)\
                                   for release_id in processed_release_ids]]
        cursor.execute("update artists set incomplete = NULL where id=?", (artist_id,))

    except IndexError:
        cursor.execute(
            "insert into artists (name, slug, incomplete) values (?, ?, ?)",
            (artist_info["name"], generate_slug(artist_info["name"], cursor, 'artists'), None)
        )

        artist_id = cursor.lastrowid
        processed_release_mbids = []

    incomplete_artist_mbids = {mbid: artist_id for (mbid, artist_id,) in query_db(db,'select incomplete, id from artists where incomplete is not null')}
    
    pool = ThreadPool(8)
    releases = get_releases(artist_info['id'], processed_release_mbids)
    pool.map(get_release, releases)

    # Dictionary of artist MBIDs to local IDs which have already been processed and can't make dummy entries in the artists table
    processed_artist_mbids = {artist_info['id']: artist_id}

    for release in releases:
        cursor.execute(
            "insert into releases (title, slug, date, type, album_art_url) values (?, ?, ?, ?, ?)",
            (release['title'],
             generate_slug(release['title'], cursor, 'releases'),
             release['date'],
             release['type'],
             release['album-art-url'])
        )
        release['local-id'] = cursor.lastrowid

        cursor.execute(
            "insert into release_colors (release_id, color1, color2, color3) values (?, ?, ?, ?)",
            (release['local-id'],
             release['palette'][0],
             release['palette'][1],
             release['palette'][2])
        )

        cursor.execute(
            "insert into release_mbid (release_id, mbid) values (?, ?)",
            (release['local-id'],
             release['id'])
        )

        for artist in release['artists']:
            try:
                if artist['artist']['id'] in processed_artist_mbids:
                    artist['artist']['local-id'] = processed_artist_mbids[artist['artist']['id']]
                elif artist['artist']['id'] in incomplete_artist_mbids:
                    artist['artist']['local-id'] = incomplete_artist_mbids[artist['artist']['id']]
                else:
                    # Make a dummy entry into the artists table
                    cursor.execute(
                        "insert into artists (name, slug, incomplete) values (?, ?, ?)",
                        (artist['artist']['name'],
                         generate_slug(artist['artist']['name'], cursor, 'artists'),
                         artist['artist']['id'])
                    )
                    artist['artist']['local-id'] = cursor.lastrowid
                    processed_artist_mbids[artist['artist']['id']] = artist['artist']['local-id']

                cursor.execute(
                    "insert into authors (release_id, artist_id) values (?, ?)",
                    (release['local-id'],
                     artist['artist']['local-id'])
                )

            except TypeError:
                pass

        for track in release['tracks']:
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

    db.commit()

musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")

if __name__ == '__main__':
    import_artist(sys.argv[1])