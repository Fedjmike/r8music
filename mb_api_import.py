#!/usr/bin/env python3

import sys, requests, arrow, musicbrainzngs
from urllib.parse import urlparse
from multiprocessing.dummy import Pool as ThreadPool

from tools import guess_wikipedia_page, get_wikipedia_summary, get_wikipedia_image, WikipediaPageNotFound, sortable_date
from model import Model, NotFound, AlreadyExists

limit = 100

class ReleaseImportError(Exception):
    pass

def get_canonical_url(url):
    """Skips through redirects to get the "actual" URL"""
    return requests.get(url).url

def get_album_art_urls(mbid, group=True):
    try:
        print("Getting album art for %s %s..." % ("release group" if group else "release", mbid))
        url_format = "http://coverartarchive.org/%s/%s/"
        url = url_format % ("release-group" if group else "release", mbid)
        art = requests.get(url).json()['images'][0]
        return (get_canonical_url(url) for url in
                (art['image'], art['thumbnails']['small']))
        
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
        
        return links
        
    except KeyError as e:
        print("Error getting links:", e)
        return {}

discogs_headers = {'User-agent': 'r8music.com'}
discogs_master_endpoint = 'https://api.discogs.com/masters/%s'
discogs_release_endpoint = 'https://api.discogs.com/releases/%s'

class NoDiscogsLink(Exception):
    pass

def get_group_mbid(release_mbid):
    return musicbrainzngs.get_release_by_id(release_mbid, includes=['release-groups'])['release']['release-group']['id']

genre_blacklist = ['Brass & Military', 'Children\'s', 'Folk, World & Country', 'Funk / Soul', 'Non-Music', 'Pop', 'Stage & Screen']

def get_discogs_tags(discogs_id, master=False):
    response = requests.get(url=discogs_master_endpoint if master else \
                                discogs_release_endpoint % discogs_id,
                            headers=discogs_headers).json()

    tags = (response["genres"] if 'genres' in response else []) + \
           (response["styles"] if 'styles' in response else [])
           
    return filter(lambda tag: tag not in genre_blacklist, tags)

def get_discogs_id(release_mbid, rels=None):
    if not rels:
        group_mbid = get_group_mbid(release_mbid)
        result = musicbrainzngs.get_release_group_by_id(group_mbid, includes=['url-rels'])

        try:
            rels = result['release-group']['url-relation-list']

        except KeyError:
            raise NoDiscogsLink()

    try:
        discogs_url = [rel['target'] for rel in rels if rel['type'] == 'discogs'][0]

    except IndexError:
        raise NoDiscogsLink()

    return discogs_url.split('/')[-1]

def prepare_artist(artist_mbid, artist_id, artist_name):
    model = Model()

    print("Getting links...")
    links = get_links(artist_mbid)
    
    for link_type, target in links.items():
        model.set_link(artist_id, link_type, target)
        
    if "wikipedia" not in links:
        try:
            print("Guessing wikipedia link...")
            links["wikipedia"] = title = guess_wikipedia_page(artist_name)
            model.set_link(artist_id, "wikipedia", title)

        except WikipediaPageNotFound:
            print("Couldn't guess wikipedia link")
    
    if "wikipedia" in links:
        print("Scraping wikipedia...")
        model.set_description(artist_id, get_wikipedia_summary(links["wikipedia"]))

        try:
            image_thumb, image = get_wikipedia_image(links["wikipedia"])
            model.set_link(artist_id, "image", image)
            model.set_link(artist_id, "image_thumb", image_thumb)

        except TypeError:
            pass

def get_release(group_mbid):
    model = Model()

    print("Querying MB for release group " + group_mbid + "...")
    result = musicbrainzngs.get_release_group_by_id(group_mbid, includes=['releases', 'url-rels'])

    try:
        release_type = result['release-group']['type']

    except KeyError:
        release_type = "Unspecified"
    release_candidates = [r for r in result['release-group']['release-list'] if 'date' in r]

    if not release_candidates:
        raise ReleaseImportError
    
    if any(model.mbid_in_links(release['id']) for release in release_candidates):
        print("Release " + release_candidates[0]['id'] + " has already been processed")
        raise ReleaseImportError

    # Gets the oldest release of the group. If it fails, ignore this release group
    release = min(release_candidates,
                  key=lambda release: arrow.get(sortable_date(release["date"])).timestamp)

    release['group-id'] = group_mbid
    release['type'] = release_type

    try:
        release['group-url-rels'] = result['release-group']['url-relation-list']

    except KeyError:
        pass

    return release

def get_group_mbids(mbid):
    print("Querying MB for release groups...")
    offset = 0
    release_groups = []
    
    while True:
        result = musicbrainzngs.browse_release_groups(mbid, limit=limit, offset=offset)
        release_groups += result['release-group-list']
        offset += limit
        if len(result['release-group-list']) != limit:
            break
        print("Getting more release groups with offset " + str(offset) +"...")

    return [release_group['id'] for release_group in release_groups]

def prepare_release(release):
    release['full-art-url'], release['thumb-art-url'] \
        = get_album_art_urls(release['group-id'])

    print("Getting deets for release " + release['id'] + "...")
    result = musicbrainzngs.get_release_by_id(release['id'], includes=['recordings', 'artists', 'url-rels'])
    mediums = sorted(result['release']['medium-list'], key=lambda m: m["position"])
    release['tracks'] = [medium['track-list'] for medium in mediums]
    release['artists'] = result['release']['artist-credit']

    try:
        release['url-rels'] = result['release']['url-relation-list']

    except KeyError:
        pass

    if 'group-url-rels' in release:
        try:
            discogs_master_id = get_discogs_id(release['group-id'], rels=release['group-url-rels'])
            release['tags'] = get_discogs_tags(discogs_master_id, master=True)

        except NoDiscogsLink:
            pass

    elif 'url-rels' in release:
        try:
            discogs_id = get_discogs_id(release['id'], rels=release['url-rels'])
            release['tags'] = get_discogs_tags(discogs_id, master=False)

        except NoDiscogsLink:
            pass

def apply_tags(tags, release_id):
    model = Model()

    for tag in tags:
        tag_id = model.get_discogs_tag_id(tag)
        model.tag_object(tag_id, release_id)

def add_release(release):
    model = Model()

    print("Adding release: ", release['title'])
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
            try:
                featured_artist_id = model.query_unique("select id from links where target=?",
                                                        artist['artist']['id'])[0]

            except NotFound:
                # Make a dummy entry into the artists table
                featured_artist_id = model.add_artist(
                    artist['artist']['name'],
                    artist['artist']['id'] #mbid
                )

            model.add_author(release_id, featured_artist_id)

        # & is in release['artists'] for some reason :o
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

    if 'tags' in release:
        apply_tags(release['tags'], release_id)

class MBID(str):
    pass

class id_(str):
    pass

def standalone_import_release_group(release_group):
    #TODO: Update specific release by id
    if isinstance(release_group, MBID):
        group_mbid = release_group

    else:
        result = musicbrainzngs.search_release_groups(releasegroup=release_group)
        group_mbid = result['release-group-list'][0]['id']
        
    import_release_group(group_mbid)

def import_release_group(group_mbid):
    try:
        release = get_release(group_mbid)

    except ReleaseImportError:
        return

    prepare_release(release)
    add_release(release)

def import_artist(artist):
    """artist may the name, mbid or local id"""

    model = Model()
    mb_type_id = model.get_link_type_id("musicbrainz")

    print("Querying MB for artist info...")
    if isinstance(artist, id_):
        artist_mbid, artist_name = \
            model.query_unique("select target, name from links join artists using (id)"
                               " where type_id=? and artists.id=?", mb_type_id, artist)

    elif isinstance(artist, MBID):
        artist_mbid = artist
        result = musicbrainzngs.get_artist_by_id(artist_mbid)
        artist_name = result['artist']['name']

    else:
        result = musicbrainzngs.search_artists(artist=artist)
        artist_mbid = result['artist-list'][0]['id']
        artist_name = result['artist-list'][0]['name']

    update_links = True
    
    #Been imported before
    try:
        (artist_id,) = model.query_unique('select id from links where type_id=?'
                                          ' and target=?', mb_type_id, artist_mbid)
        print("Already imported, updating...")
        update_links = False

    #Not in db
    except NotFound:
        artist_id = model.add_artist(artist_name, artist_mbid)

    if update_links:
        prepare_artist(artist_mbid, artist_id, artist_name)
        
    pool = ThreadPool(8)
    group_mbids = get_group_mbids(artist_mbid)
    pool.map(import_release_group, group_mbids)

musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")

if __name__ == '__main__':
    import_artist(sys.argv[1])
