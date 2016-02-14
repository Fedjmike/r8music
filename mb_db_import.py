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
    cur.execute("select artist_credit from artist_credit_name where artist = %s", (_id,))
    artist_credit_ids = [ac_id for (ac_id,) in cur.fetchall()]
    print(artist_credit_ids)
    release_group_ids = []
    for artist_credit in artist_credit_ids:
        cur.execute("select id from release_group where artist_credit = %s", (artist_credit,))
        for (release_group_id,) in cur.fetchall():
            release_group_ids.append(release_group_id)
    print(release_group_ids)
    for release_group_id in release_group_ids:
        cur.execute("select id from release where release_group = %s", (release_group_id,))
        release_ids = [_id for (_id,) in cur.fetchall()]
        print(release_ids)
        for release_id in release_ids:
            cur.execute("select * from release_country where release = %s", (release_id,))


if __name__ == '__main__':
    gid = gid_from_name(sys.argv[1])
    import_artist(gid)

