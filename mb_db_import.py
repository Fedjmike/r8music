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

# TODO:
    # Finish writing DB calls
    # Merge DB calls
    # Populate local database
    # Dupe avoidance
def import_artist(gid):
    mb_db = psycopg2.connect(user=user, database=database, password=password)
    cur = mb_db.cursor()
    cur.execute("SELECT id FROM artist WHERE gid = %s", (gid,))
    (_id,) = cur.fetchone()
    print(_id)
    cur.execute("SELECT artist_credit FROM artist_credit_name WHERE artist = %s", (_id,))
    artist_credit_ids = [ac_id for (ac_id,) in cur.fetchall()]
    print(artist_credit_ids)
    release_group_ids = []
    for artist_credit in artist_credit_ids:
        cur.execute("SELECT id FROM release_group WHERE artist_credit = %s", (artist_credit,))
        for (release_group_id,) in cur.fetchall():
            release_group_ids.append(release_group_id)
    print(release_group_ids)
    release_ids = []
    for release_group_id in release_group_ids:
        cur.execute("SELECT id FROM ( \
                        SELECT id FROM release WHERE release_group = %s r \
                        LEFT JOIN release_country c ON r.id = c.release \
                            ORDER BY date_year nulls last, \
                                     date_month nulls last, \
                                     date_day nulls last \
                        ) LIMIT 1", (release_group_id,))
        release_ids.append(cur.fetchone()[0])

if __name__ == '__main__':
    gid = gid_from_name(sys.argv[1])
    import_artist(gid)

