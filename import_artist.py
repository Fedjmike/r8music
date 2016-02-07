import musicbrainzngs
import sqlite3
import sys
import re
import json
from unidecode import unidecode

# From http://flask.pocoo.org/snippets/5/
_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        result.extend(unidecode(word).split())
    return delim.join(result)

def get_releases(mbid):
    result = musicbrainzngs.get_artist_by_id(mbid, includes=['release-groups']) 
    release_groups = result['artist']['release-group-list']
    releases = []
    for group in release_groups:
        result = musicbrainzngs.get_release_group_by_id(group['id'], includes=['releases'])
        release = result['release-group']['release-list'][0]
        print(json.dumps(release, sort_keys=True, indent=4, separators=(',', ': ')))
        try:
            release['type'] = group['type']
        except KeyError:
            release['type'] = 'Unspecified'

        releases.append(release)
    return releases

def get_tracks(release_id):
    result = musicbrainzngs.get_release_by_id(release_id, includes=['recordings'])
    tracks = result['release']['medium-list'][0]['track-list']
    return tracks

def import_artist(artist_name):
    result = musicbrainzngs.search_artists(artist=artist_name)
    artist_info = result['artist-list'][0]

    con = sqlite3.connect('sample.db')
    cursor = con.cursor()

    cursor.execute(
        "insert into artists (name, slug) values (?, ?)",
        (artist_info["name"], slugify(artist_info["name"]))
    )

    artist_id = cursor.lastrowid
    releases = get_releases(artist_info['id'])

    for release in releases:
        cursor.execute(
            "insert into releases (title, date, artist_id, type) values (?, ?, ?, ?)",
            (release['title'], release['date'], artist_id, release['type'])
        )
        release['local-id'] = cursor.lastrowid
        try:
            tracks = get_tracks(release['id'])
            for track in tracks:
                cursor.execute(
                    "insert into tracks (title, runtime, release_id) values (?, ?, ?)",
                    (track['recording']['title'], track['recording']['length'], release['local-id'])
                )
        except:
            pass
    con.commit()

musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
musicbrainzngs.musicbrainz.VALID_RELEASE_TYPES = ['nat', 'album', 'ep', 'other', 'compilation', 'soundtrack', 'live', 'remix', 'dj-mix', 'mixtape/street']

if __name__ == '__main__':
    import_artist(sys.argv[1])