#!/usr/bin/env python3

import requests, arrow, musicbrainzngs
from urllib.parse import urlparse
from multiprocessing.dummy import Pool as ThreadPool

from tools import guess_wikipedia_page, get_wikipedia_summary, get_wikipedia_images
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
    other_types = {'www.facebook.com': 'facebook',
                   'twitter.com': 'twitter',
                   'plus.google.com': 'google plus',
                   'en.wikipedia.org': 'wikipedia'}
                   
    def split_link(_type, url):
        _, domain, path, _, _, _ = urlparse(url)
        if domain in other_types:
            _type = other_types[domain]
            
        target = path[len("/wiki/"):] \
                 if "wikipedia" == _type and path.startswith("/wiki/") \
                 else url
        return _type, target
            
    try:
        #todo optimize get_artists calls
        result = musicbrainzngs.get_artist_by_id(artist_mbid, includes=['url-rels'])
        links = {}
        for item in result['artist']['url-relation-list']:
            _type, target = split_link(item['type'], item['target'])
            links[_type] = target
    except KeyError as e:
        print("Error getting links:", e)
    return links

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
        
        fulldate = lambda date: date + "-12-31" if len(date) == 4 else \
                                arrow.get(date + '-01').replace(months=+1, days=-1).format('YYYY-MM-DD') if len(date) == 7 else \
                                date
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

    print("Getting deets for release " + release['id'] + "...")
    result = musicbrainzngs.get_release_by_id(release['id'], includes=['recordings', 'artists'])
    mediums = sorted(result['release']['medium-list'], key=lambda m: m["position"])
    release['tracks'] = [medium['track-list'] for medium in mediums]
    release['artists'] = result['release']['artist-credit']

class MBID(str):
    pass
    
def import_artist(artist):
    """artist may either be the name or MBID"""
    
    print("Querying MB for artist info...")
    if isinstance(artist, MBID):
        artist_mbid = artist
        result = musicbrainzngs.get_artist_by_id(artist_mbid)
        artist_name = result['artist']['name']
    else:
        result = musicbrainzngs.search_artists(artist=artist)
        artist_mbid = result['artist-list'][0]['id']
        artist_name = result['artist-list'][0]['name']

    model = Model()

    mb_type_id = model.get_link_type_id("musicbrainz")
    
    try:
        #Imported incompletely
        (artist_id,) = model.query_unique('select id from artists where incomplete=?', artist_mbid)
        processed_release_mbids = [
            row['target'] for row in
            model.query('select target from links l join authorships a on l.id = a.release_id where artist_id=? and type_id=?', artist_id, mb_type_id)
        ]
        
        model.execute('update artists set incomplete = NULL where id=?', artist_id)

    except NotFound:
        try:
            #Complete
            (artist_id,) = model.query_unique('select id from links where type_id=? and target=?', mb_type_id, artist_mbid)
            print("Already imported")
            return

        #Not in db
        except NotFound:
            artist_id = model.add_artist(artist_name, artist_mbid)
            processed_release_mbids = []

    print("Getting links...")
    links = get_links(artist_mbid)
    for link_type, target in links.items():
        model.set_link(artist_id, link_type, target)
            
    if "wikipedia" not in links:
        print("Guessing wikipedia link...")
        links["wikipedia"] = title = guess_wikipedia_page(artist_name)
        model.set_link(artist_id, "wikipedia", title)

    print("Scraping wikipedia...")
    model.add_artist_description(artist_id, get_wikipedia_summary(links["wikipedia"]))
    try:
        image_thumb, image = next(get_wikipedia_images(links["wikipedia"]))
        model.set_link(artist_id, "image", image)
        model.set_link(artist_id, "image_thumb", image_thumb)
    except StopIteration:    
        pass
        
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
                        artist['artist']['id'], #mbid
                        incomplete=True
                    )
                    
                    processed_artist_mbids[artist['artist']['id']] = featured_artist_id

                model.add_author(release_id, featured_artist_id)

            except TypeError:
                pass

        for side, tracks in enumerate(release['tracks']):
            for track in tracks:
                try:
                    length = track['recording']['length']
                except KeyError:
                    length = None
                model.add_track(
                    release_id,
                    track['recording']['title'],
                    int(track['position']),
                    side,
                    length
                )

musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")

if __name__ == '__main__':
    import_artist(sys.argv[1])
