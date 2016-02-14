import musicbrainzngs
import psycopg2
import sys
from config import database, user, password

def gid_from_name(artist_name):
    print("Querying MB for artist info...")
    musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
    result = musicbrainzngs.search_artists(artist=artist_name)
    gid = result['artist-list'][0]['id']
    print(gid)
    return gid

def import_artist(gid):
    mb_db = psycopg2.connect(user=user, database=database, password=password)
    cur = mb_db.cursor()
    cur.execute("select id from artist where gid = %s", (gid,))
    (_id,) = cur.fetchone()
    print(_id)
    cur.execute("select entity1 from l_artist_release_group where entity0 = %s", (_id,))
    print(cur.fetchall())
    release_group_ids = [id for (id,) in cur.fetchall()]
    print(release_group_ids)

if __name__ == '__main__':
    gid = gid_from_name(sys.argv[1])
    import_artist(gid)

