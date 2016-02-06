import musicbrainzngs
import sqlite3
import json
import re
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
    releases = result['artist']['release-group-list']
    return releases

def import_artist(artist_name):
    result = musicbrainzngs.search_artists(artist=artist_name)
    artist_info = result['artist-list'][0]

    con = sqlite3.connect('sample.db')
    cursor = con.cursor()

    cursor.execute(
        "insert into artists (name, url) values (?, ?)",
        (artist_info["name"], slugify(artist_info["name"]))
    )

    artist_id = cursor.lastrowid
    releases = get_releases(artist_info['id'])
    for release in releases:
        cursor.execute(
            "insert into releases (title, year, artist_id) values (?, ?, ?)",
            (release['title'], release['first-release-date'], artist_id)
        )

    con.commit()

    print("DANK")
    # result = musicbrainzngs.get_artist_by_id(artist_info['id'], includes=['release-groups'])
    # print(json.dumps(result, sort_keys=True, indent=4, separators=(',', ': ')))

musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
import_artist("nujabes")
# get_releases("1595addf-f76b-450a-a097-af852ff35f27")