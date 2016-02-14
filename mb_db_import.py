import musicbrainzngs
import psycopg2
import sys
from config import database, user, password


def gid_from_name(name):
    print("Querying MB for artist info...")
    musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
    result = musicbrainzngs.search_artists(artist=artist_name)
    gid = result['artist-list'][0]['id']
    return gid

def import_artist(gid):
    mb_db = psycopg2.connect(user=user, database=database, password=password)
    cur = mb_db.cursor()
    (_id,) = cur.execute("select id from artist where gid = %s", (gid,))
    print(_id)


if __name__ == '__main__':
    gid = gid_from_name(sys.argv[1])
    import_artist(gid)

