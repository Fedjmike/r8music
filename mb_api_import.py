#/usr/bin/python3

import musicbrainzngs
import sqlite3, sys, requests
import arrow
from multiprocessing import Pool
from multiprocessing.dummy import Pool as ThreadPool
import import_tools
from model import Model, NotFound

album_art_base_url = 'http://coverartarchive.org/release-group/'

def get_canonical_url(url):
    return requests.get(url).url

def get_album_art_urls(release_group_id):
    print("Getting album art for release group " + release_group_id + "...")
    r = requests.get(album_art_base_url + release_group_id + '/')
    try:
        return (get_canonical_url(url) for url in
                (r.json()['images'][0]['image'],
                 r.json()['images'][0]['thumbnails']['large']))
    except ValueError:
        return None, None

def get_links(artist_mbid):
    result = musicbrainzngs.get_artist_by_id(artist_mbid, includes=['url-rels'])
    other_types = {'www.facebook.com': 'facebook',
                   'twitter.com': 'twitter',
                   'plus.google.com': 'google plus'}
    try:
        links = {}
        for item in result['artist']['url-relation-list']:
            domain = item['target'].split('/')[2]
            if domain in other_types:
                links[other_types[domain]] = item['target']
                continue
            links[item['type']] = item['target']
        return links
    except KeyError:
        return None

def get_releases(mbid, processed_release_mbids):
    print("Querying MB for release groups...")
    result = musicbrainzngs.get_artist_by_id(mbid, includes=['release-groups']) 
    release_groups = result['artist']['release-group-list']
    releases = []
    for group in release_groups:
        print("Querying MB for release group " + group['id'] + "...")
        result = musicbrainzngs.get_release_group_by_id(group['id'], includes=['releases'])
        # Gets the oldest release of the group. If it fails, ignore this release group
        release_candidates = [x for x in result['release-group']['release-list'] if 'date' in x]
        if not release_candidates:
            continue
        
        fulldate = lambda date: date + "-12-31" if len(date) == 4 else date
        release = min(release_candidates,
                      key=lambda release: arrow.get(fulldate(release["date"])).timestamp)

        if release['id'] in processed_release_mbids:
            print("Release " + release['id'] + " has already been processed")
            continue

        release['group-id'] = group['id']
        release['type'] = group['type'] if 'type' in group else 'Unspecified'

        releases.append(release)
    return releases

def prepare_release(release):
    release['full-art-url'], release['thumb-art-url'] \
        = get_album_art_urls(release['group-id'])

    if release['thumb-art-url']:
        release['palette'] = import_tools.get_palette(release['thumb-art-url'])
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
    artist_mbid = artist_info['id']

    model = Model()

    # Check if the artist's MBID matches the 'incomplete' field of any other artists
    # If so, get the artist_id and set the 'incomplete' field to NULL
    # If not, import as a new artist into the database
    try:
        (artist_id,) = model.query_unique('select id from artists where incomplete=?', artist_mbid)
    
        processed_release_mbids = [
            row['mbid'] for row in
            model.query('select mbid from release_externals natural join'
                        ' (select release_id from authorships where artist_id=?)', artist_id)
        ]
        
        model.execute('update artists set incomplete = NULL where id=?', artist_id)

    except NotFound:
        artist_id = model.add_artist(artist_info['name'], import_tools.get_description(artist_info['name']))
        processed_release_mbids = []

    print("Getting links...")
    links = get_links(artist_mbid)
    if links:
        for _type in links:
            try:
                link_type_id = model.query_unique("select id from link_types where link_type = ?", _type)[0]
            except NotFound:
                link_type_id = model.insert("insert into link_types (link_type) values (?)", _type)
            model.insert("insert into artist_links (artist_id, link_type_id, link_target) values (?, ?, ?)", artist_id, link_type_id, links[_type])

    pool = ThreadPool(8)
    releases = get_releases(artist_mbid, processed_release_mbids)
    pool.map(prepare_release, releases)

    # Dictionary of artist MBIDs to local IDs which have already been processed and can't make dummy entries in the artists table
    processed_artist_mbids = dict(model.query('select incomplete, id from artists where incomplete is not null'))
    processed_artist_mbids[artist_mbid] = artist_id

    for release in releases:
        release_id = model.add_release(
            release['title'],
            release['date'],
            release['type'],
            release['full-art-url'],
            release['thumb-art-url'],
            release['palette'],
            release['id'] #mbid
        )
        
        for artist in release['artists']:
            try:
                if artist['artist']['id'] in processed_artist_mbids:
                    featured_artist_id = processed_artist_mbids[artist['artist']['id']]
                else:
                    # Make a dummy entry into the artists table
                    featured_artist_id = model.add_artist(
                        artist['artist']['name'],
                        import_tools.get_description(artist['artist']['name']),
                        artist['artist']['id'] #mbid
                    )
                    
                    processed_artist_mbids[artist['artist']['id']] = featured_artist_id

                model.add_author(release_id, featured_artist_id)

            except TypeError:
                pass

        for track in release['tracks']:
            try:
                length = track['recording']['length']
            except KeyError:
                length = None
            model.add_track(
                release_id,
                track['recording']['title'],
                int(track['position']),
                length
            )

musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")

if __name__ == '__main__':
    import_artist(sys.argv[1])
