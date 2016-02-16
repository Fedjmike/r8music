import musicbrainzngs
import psycopg2
import sys, sqlite3
import import_tools
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
    local_db = sqlite3.connect('sample.db')
    lcr = local_db.cursor()
    mb_db = psycopg2.connect(user=user, database=database, password=password)
    cr = mb_db.cursor()
    cr.execute("SELECT id, name FROM artist WHERE gid = %s", (gid,))
    artist = {}
    ((artist['id'], artist['name']),) = cr.fetchall()
    print(artist['id'])
    cr.execute("SELECT artist_credit FROM artist_credit_name WHERE artist = %s", (artist['id'],))
    artist_credit_ids = [ac_id for (ac_id,) in cr.fetchall()]
    print(artist_credit_ids)
    release_group_ids = []
    # Do this with a join
    for artist_credit in artist_credit_ids:
        cr.execute("SELECT id FROM release_group WHERE artist_credit = %s", (artist_credit,))
        for (release_group_id,) in cr.fetchall():
            release_group_ids.append(release_group_id)
    print(release_group_ids)
    release_ids = []
    for release_group_id in release_group_ids:
        cr.execute("select id from (select id from release where release_group = %s) r left join release_country c on r.id = c.release order by date_year nulls last, date_month nulls last, date_day nulls last limit 1", (release_group_id,))
        release_ids.append(cr.fetchone()[0])
    print(release_ids)
    releases = []
    for release_id in release_ids:
        release = {}
        cr.execute("select position, name, length from track where medium = (select id from medium where release = %s order by position limit 1)", (release_id,))
        tracks = cr.fetchall()
        print(tracks)
        release['tracks'] = tracks

        cr.execute("select cover_art_url from release_coverart where id = %s", (release_id,))
        try:
            # TODO: Actually get the cover art url lel
            (release['cover_art_url'],) = cr.fetchone()
        except TypeError:
            release['cover_art_url'] = None
        print(release['cover_art_url'])
    #lcr.execute(
     #   "insert into artists (name, slug, incomplete) values (?, ?, ?)",
      #  (artist['name'], import_tools.slugify(artist['name']), None)
    #)

    local_db.commit()

if __name__ == '__main__':
    gid = gid_from_name(sys.argv[1])
    import_artist(gid)

