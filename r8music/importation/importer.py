import time, re, requests, wikipedia, musicbrainzngs, discogs_client
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, unquote

from django.conf import settings
from django.db import transaction

from r8music.music.models import (
    Artist, Release, Track, generate_slug_tracked,
    DiscogsTag, ArtistExternalLink, ReleaseExternalLink
)
from .models import (
    ArtistMBLink, ArtistMBImportation, ReleaseMBLink, ReleaseDuplication,
    ArtistMBIDMap, ReleaseMBIDMap, DiscogsTagMap
)
from r8music.actions.models import SaveAction, ListenAction, RateAction, PickAction, ActiveActions

from .utils import (
    uniqify, mode_items, query_and_collect,
    musicbrainz_url, get_release_type_from_mb_str
)
from .chromatography import get_palette

class Importer:
    mb_browse_limit = 100
    
    discogs_genre_blacklist = set([
        "Brass & Military", "Children's", "Folk, World, & Country",
        "Funk / Soul", "Non-Music", "Pop", "Stage & Screen"
    ])
    
    def __init__(self, requests=requests, musicbrainz=musicbrainzngs, wikipedia=wikipedia, discogs_client=discogs_client):
        self.requests = requests
        self.musicbrainz = musicbrainz
        self.wikipedia = wikipedia
        self.discogs = discogs_client.Client(settings.DISCOGS_USERAGENT_STRING)
        
        musicbrainzngs.set_useragent(*settings.MUSICBRAINZ_USERAGENT)
        
    def get_canonical_url(self, url):
        """Skip through redirects to get the "actual" URL"""
        return self.requests.get(url).url
    
    # Wikipedia
    
    en_wikipedia_url_pattern = re.compile("en.wikipedia.org/wiki/(/?.*)")
    
    def guess_wikipedia_page(self, artist_name):
        music_categories = ["musician", "band", "rapper", "artist", "singer", "songwriter"]
        is_music_page = lambda str: any(category in str for category in music_categories)
        
        try:
            page = self.wikipedia.page(artist_name)
            
            for link in page.links:
                if "disambiguation" in link:
                    #Opening a disambiguation page will raise a DisambiguationError
                    self.wikipedia.page(link)
            
            #Confirm the page refers to an artist
            return page if page.summary and is_music_page(page.summary) else None
            
        except self.wikipedia.exceptions.PageError:
            return None
            
        except self.wikipedia.exceptions.DisambiguationError as disambiguation:
            #Identify the correct option by the title, which usually contains
            #something like "(band)"
            title = next(filter(is_music_page, disambiguation.options), None)
            return self.wikipedia.page(title) if title else None
            
    def get_wikipedia_images(self, wikipedia_page):        
        try:
            html = BeautifulSoup(wikipedia_page.html(), features="html.parser")
            image_link = html.select(".infobox a.image")[0]
            image_url = image_link["href"]
            
        except (IndexError, KeyError):
            return None
            
        else:            
            #srcset is a list of images of different sizes, with scales
            thumbs = re.findall("(?:([^, ]*) ([\d.]*x))", image_link.img["srcset"])
            #Get the largest image
            thumb_url, scale = max(thumbs, key=lambda thumb_scale: thumb_scale[1])
            
            #Turn the URLs (which might be relative) into absolute URLs
            absolute_urls = [urljoin(wikipedia_page.url, url) for url in [image_url, thumb_url]]
            
            return absolute_urls
            
    def query_wikipedia(self, artist_name, wikipedia_url=None):        
        wikipedia_page = None
        
        if wikipedia_url:
            #Only use pages on the english wikipedia
            #(because of limitations of the wikipedia library)
            match = self.en_wikipedia_url_pattern.search(wikipedia_url)
            
            if match:
                try:
                    #Unicode characters in the title may be HTTP encoded
                    title = unquote(match.group(1))
                    wikipedia_page = self.wikipedia.page(title, auto_suggest=False)
                    
                except self.wikipedia.exceptions.PageError:
                    pass
            
        if not wikipedia_page:
            wikipedia_page = self.guess_wikipedia_page(artist_name) 
            
        if not wikipedia_page:
            return None, None, None
            
        else:
            return (
                #Only return the URL if it wasn't provided
                (wikipedia_page.url if wikipedia_url is None else None),
                wikipedia_page.summary,
                self.get_wikipedia_images(wikipedia_page)
            )
            
    # Artists (MusicBrainz)
    
    class ArtistResponse:
        """Contains the response(s) from queries to MusicBrainz etc.
           The JSON (from MusicBrainz) can either be from a full artist query,
           or from the artist-credits key from a release query."""
        def __init__(self, json, extra_links=None, description=None, images=None):
            self.json = json
            self.extra_links = extra_links or []
            self.description = description
            self.image_url, self.image_thumb_url = images if images else (None, None)
        
    def query_artist(self, artist_mbid):
        artist_json = self.musicbrainz.get_artist_by_id(artist_mbid, includes=["url-rels"])["artist"]
        
        url_relations = artist_json.get("url-relation-list", [])
        candidates = (rel["target"] for rel in url_relations if rel["type"] == "wikipedia")
        wikipedia_url = next(candidates, None)
        
        guessed_wikipedia_url, description, images = \
            self.query_wikipedia(artist_json["name"], wikipedia_url)
        
        extra_links = [guessed_wikipedia_url] if guessed_wikipedia_url else []
        return self.ArtistResponse(artist_json, extra_links, description, images)
        
    def replace_artist(self, existing_artist, artist):
        #Move related objects onto the new artist object, except those which
        #have been recreated in the importation.
        for related_model in [ArtistMBLink, ArtistMBImportation, Release.artists.through]:
            related_model.objects.filter(artist=existing_artist).update(artist=artist)
        
        existing_artist.delete()
        
    def create_artist(self, artist_response, slug, existing_artist=None):        
        artist = Artist.objects.create(
            name=artist_response.json["name"],
            slug=slug,
            description=artist_response.description,
            image_url=artist_response.image_url,
            image_thumb_url=artist_response.image_thumb_url
        )
        
        ArtistMBImportation.objects.create(artist=artist)
        
        external_links = [
            ArtistExternalLink(artist=artist, url=url_relation["target"], name=url_relation["type"])
            for url_relation in artist_response.json.get("url-relation-list", [])
        ]
        
        external_links += [
            ArtistExternalLink(artist=artist, url=url, name=urlparse(url).netloc)
            for url in artist_response.extra_links
        ]
        
        external_links.append(ArtistExternalLink(
            artist=artist, name="musicbrainz",
            url=musicbrainz_url(artist_response.json["id"], artist=True)
        ))
        
        ArtistExternalLink.objects.bulk_create(external_links)
        
        if existing_artist:
            self.replace_artist(existing_artist, artist)
        
        else:
            ArtistMBLink.objects.create(artist=artist, mbid=artist_response.json["id"])
        
    def create_artists(self, artist_responses):
        mbids = [response.json["id"] for response in artist_responses]
        
        #Artists already in the database
        artists_for_update = {
            artist.mb_link.mbid: artist for artist
            in Artist.objects.filter(mb_link__mbid__in=mbids).select_related("mb_link")
        }
        
        used_slugs = set(Artist.objects.values_list("slug", flat=True))
        
        for artist_response in artist_responses:
            existing_artist = artists_for_update.get(artist_response.json["id"], None)
            
            slug = existing_artist.slug if existing_artist \
                else generate_slug_tracked(used_slugs, artist_response.json["name"])
            
            self.create_artist(artist_response, slug, existing_artist)
                
        return ArtistMBIDMap()
        
    # Discogs (used for populating tags)
    
    discogs_url_pattern = re.compile("discogs.com(/.*)?/(release|master)/(\d*)")
    discogs_ratelimit_wait_time = 15 #in seconds
    
    def find_discogs_url(self, url_relations):
        candidates = (rel["target"] for rel in url_relations if rel["type"] == "discogs")
        return next(candidates, None)
    
    def get_discogs_id(self, discogs_url):
        match = self.discogs_url_pattern.search(discogs_url)
        return match.group(3) if match else None
    
    def query_discogs_tags(self, discogs_id, is_master=False):
        #The discogs client currently has no rate limiting, so retry after a pause.
        while True:
            try:
                release = (self.discogs.master if is_master else self.discogs.release)(discogs_id)
                tags = (release.genres or []) + (release.styles or [])
                return set(tags) - self.discogs_genre_blacklist
                
            except discogs_client.exceptions.HTTPError as e:
                if e.status_code == 429: #"Too Many Requests"
                    time.sleep(self.discogs_ratelimit_wait_time)
                    continue
                    
                return set()
    
    def query_discogs(self, release_json, release_group_json):
        def get(json, is_master=False):
            url = self.find_discogs_url(json["url-relation-list"]) \
                if "url-relation-list" in json else None
            id = self.get_discogs_id(url) if url else None
            tags = self.query_discogs_tags(id, is_master) if id else set()
            return id, tags
        
        #Query both the release and its master and combine their tags
        discogs_release_id, release_tags = get(release_json)
        discogs_master_id, master_tags = get(release_group_json, is_master=True)
        tags = release_tags | master_tags
        return discogs_release_id, discogs_master_id, list(tags)
        
    # Cover art archive
    
    def select_cover_art(self, art_json):
    	#See https://musicbrainz.org/doc/Cover_Art_Archive/API
    	
        if len(art_json["images"]) == 0:
            return None
        
        try:
            is_front = lambda image_json: image_json["front"]
            image = next(filter(is_front, art_json["images"]))
            
        except StopIteration:
            image = art_json["images"][0]
            
        art_urls = {
            "max": image["image"],
            #"small" and "large" are deprecated keys corresponding to "250" and "500"
            "250": image["thumbnails"].get("250", None) or image["thumbnails"].get("small", None),
            "500": image["thumbnails"].get("500", None) or image["thumbnails"].get("large", None)
        }
        
        #The cover art archive gives links which serve the image through a redirect
        art_urls = {size: self.get_canonical_url(url) for size, url in art_urls.items()}
        return art_urls
        
    def query_cover_art(self, release_mbid, release_group_mbid):
        for getter, mbid in [
            #Prefer cover art specific to the release
            (self.musicbrainz.get_image_list, release_mbid),
            (self.musicbrainz.get_release_group_image_list, release_group_mbid)
        ]:
            try:
                art_urls = self.select_cover_art(getter(mbid))
                
                if art_urls:
                    return art_urls
            
            except (self.musicbrainz.ResponseError, self.musicbrainz.NetworkError):
                pass
            
        return None
        
    # Querying releases
    
    class ReleaseResponse:
        def __init__(self, release_json, release_group_json, art_urls, discogs_tags):
            self.json, self.group_json, self.art_urls, self.discogs_tags \
                = release_json, release_group_json, art_urls, discogs_tags
    
    def browse_release_groups(self, artist_mbid, includes=[]):
        def query(limit, offset):
            return self.musicbrainz.browse_release_groups(
                artist_mbid, includes=includes,
                limit=limit, offset=offset
            )["release-group-list"]
        
        return query_and_collect(query, limits=self.mb_browse_limit)
    
    def browse_releases(self, release_group_mbid, includes=[]):
        def query(limit, offset):
            return self.musicbrainz.browse_releases(
                release_group=release_group_mbid, includes=includes,
                limit=limit, offset=offset
            )["release-list"]
        
        return query_and_collect(query, limits=self.mb_browse_limit)
        
    def select_release(self, release_jsons):
        def track_count(release):
            return sum(medium["track-count"] for medium in release["medium-list"])
        
        def best_date(release):
            #Prefer earlier years, then fuller dates, then earlier dates
            return (release["date"][:4], -len(release["date"]), release["date"])
        
        #Assume that releases with unusual track counts (non-mode) are not canonical
        releases_of_mode_track_count = mode_items(release_jsons, key=track_count)
        
        #Better if they have a date
        those_with_dates = [r for r in releases_of_mode_track_count if "date" in r]
        
        if those_with_dates:
            return min(those_with_dates, key=best_date)
            
        else:
            return next(iter(releases_of_mode_track_count), None)

    def query_release(self, release_group_json):
        release_jsons = self.browse_releases(
            release_group_json["id"], includes=["recordings", "url-rels"]
        )
        
        if not release_jsons:
            #Cannot be imported
            return None
        
        release_json = self.select_release(release_jsons)
        
        art_urls = self.query_cover_art(release_json["id"], release_group_json["id"])
        _, _, discogs_tags = self.query_discogs(release_json, release_group_json)
        
        return self.ReleaseResponse(
            release_json, release_group_json, art_urls, discogs_tags
        )
        
    def query_all_releases(self, artist_response):
        return filter(lambda x: x is not None, [
            self.query_release(release_group_json)
            for release_group_json in self.browse_release_groups(
                artist_response.json["id"], includes=["artist-credits", "url-rels"]
            )
        ])
        
    def query_single_release(self, release_group_mbid):
        release_group_json = self.musicbrainz.get_release_group_by_id(
            release_group_mbid, includes=["artist-credits", "url-rels"]
        )["release-group"]
        return self.query_release(release_group_json)
    
    #
    
    class UnsuitableReplacementError(Exception):
        pass
    
    def create_featured_artists(self, release_responses, artist_map):        
        featured_artists = (
            self.ArtistResponse(artist_credit["artist"])
            for response in release_responses
            for artist_credit in response.group_json["artist-credit"]
            if isinstance(artist_credit, dict)
                and artist_credit["artist"]["id"] not in artist_map
        )
        
        #Artists may have featured in multiple releases
        featured_artists = uniqify(featured_artists, key=lambda response: response.json["id"])
        
        artist_map = self.create_artists(featured_artists)
        
        return artist_map
        
    def create_tracks(self, release_json, release):
        Track.objects.bulk_create([
            Track(
                release_id=release.id,
                title=track["recording"]["title"],
                runtime=track["recording"].get("length", None),
                position=int(track["position"]),
                side=int(medium["position"])
            )
            for medium in release_json["medium-list"]
            for track in medium["track-list"]
        ])
        
        return release.tracks
        
    def replace_tracks(self, existing_release, release):
        tracks = list(release.tracks.all())
        
        #Move actions from the existing tracks onto matching tracks in the new release
        for existing_track in existing_release.tracks.exclude(pick_actions=None):
            matching_tracks = (track for track in tracks if track.title == existing_track.title)
            matching_track = next(matching_tracks, None)
            
            #Without a matching track for an existing track which has actions, the
            #release replacement must be aborted
            if not matching_track:
                raise self.UnsuitableReplacementError()
            
            #Each new track can only match one existing track
            tracks.remove(matching_track)
            
            existing_track.pick_actions.update(track=matching_track)
        
    def replace_release(self, existing_release, release):
        #Move related objects to the new release object
        for related_model in [SaveAction, ListenAction, RateAction, ActiveActions]:
            related_model.objects.filter(release=existing_release).update(release=release)
        
        #The new release object was given a temporary slug
        release.slug = existing_release.slug
        
        existing_release.delete()
        
        #Save the slug now that a clash is avoided
        release.save()
        
    def create_release(
        self, release_json, release_group_json, art_urls,
        slug, existing_release, artist_map
    ):
        """Can raise UnsuitableReplacementError"""
        
        if art_urls:
            extra_args = {
                "art_url_250": art_urls["250"],
                "art_url_500": art_urls["500"],
                "art_url_max": art_urls["max"]
            }
            
            #Download the cover art and extract a palette of the three main colours
            extra_args["colour_1"], extra_args["colour_2"], extra_args["colour_3"] \
                = get_palette(art_urls["500"])
                
        else:
            extra_args = {}
        
        if "type" in release_group_json:
            extra_args["type"] = get_release_type_from_mb_str(release_group_json["type"])
        
        release = Release.objects.create(
            title=release_json["title"],
            release_date=release_json["date"] if "date" in release_json else None,
            #Use a temporary slug if the release is being updated (i.e. temporarily duplicated)
            slug=slug if not existing_release else slug + "-[new]",
            **extra_args
        )
        
        tracks = self.create_tracks(release_json, release)
        
        if existing_release:
            self.replace_tracks(existing_release, release)
            self.replace_release(existing_release, release)
        
        ReleaseMBLink.objects.create(
            release=release,
            release_mbid=release_json["id"],
            release_group_mbid=release_group_json["id"]
        )
        
        #Uniqify the contributing artists (who may appear multiple times)
        artists_mbids = set(
            artist_credit["artist"]["id"]
            for artist_credit in release_group_json["artist-credit"]
            #artist-credit can include joining phrases (like "&")
            if isinstance(artist_credit, dict)
        )
        
        Release.artists.through.objects.bulk_create([
            Release.artists.through(
                release=release,
                artist_id=artist_map.get(artist_mbid)
            )
            for artist_mbid in artists_mbids
        ])
        
        ReleaseExternalLink.objects.create(
            release=release, name="musicbrainz", url=musicbrainz_url(release_json["id"])
        )
        
        ReleaseExternalLink.objects.bulk_create([
            ReleaseExternalLink(
                release=release, url=url_relation["target"], name=url_relation["type"]
            )
            for url_relation in
                release_json.get("url-relation-list", [])
                + release_group_json.get("url-relation-list", [])
        ])
        
    def create_releases(self, release_responses, artist_map):        
        #Those releases already imported
        #(identified by group MBID, as a different release may have been selected)
        releases_for_update = {
            release.mb_link.release_group_mbid: release
            for release in Release.objects.filter(mb_link__release_group_mbid__in=[
                response.group_json["id"] for response in release_responses
            ]).select_related("mb_link")
        }
        
        used_slugs = set(Release.objects.values_list("slug", flat=True))
        
        for response in release_responses:
            existing_release = releases_for_update.get(response.group_json["id"], None)
            
            try:
                #Try replacing the existing release
                with transaction.atomic():
                    self.create_release(
                        response.json, response.group_json, response.art_urls,
                        existing_release.slug, existing_release, artist_map
                    )
                
            #AttributeError is raised when existing_release is None
            #UnsuitableReplacementError means the existing release must remain
            except (AttributeError, self.UnsuitableReplacementError):
                if existing_release:
                    #Only the updated version retains the link to MusicBrainz
                    existing_release.mb_link.delete()
                
                slug = generate_slug_tracked(used_slugs, response.json["title"])
                
                release = self.create_release(
                    response.json, response.group_json, response.art_urls,
                    slug, None, artist_map
                )
                
                if existing_release:
                    ReleaseDuplication.objects.create(original=existing_release, updated=release)
        
        return ReleaseMBIDMap()
        
    def create_tags_and_taggings(self, release_responses, release_map):
        tags_map = DiscogsTagMap()
        
        new_discogs_tags = set(
            tag_name for response in release_responses
            for tag_name in response.discogs_tags
            if tag_name not in tags_map
        )
        
        #(Can't be bulk created because DiscogsTag uses model inheritance)
        for tag_name in new_discogs_tags:
            DiscogsTag.objects.create(discogs_name=tag_name, name=tag_name)
        
        tags_map.update()
        
        for response in release_responses:
            for tag_name in response.discogs_tags:
                if not tags_map.get(tag_name):
                    print(response.json["title"], tag_name)
        
        Release.tags.through.objects.bulk_create([
            Release.tags.through(
                release_id=release_map.get(response.json["id"]),
                tag_id=tags_map.get(tag_name)
            )
            for response in release_responses
            for tag_name in response.discogs_tags
        ])
        
    def create_from_release_responses(self, release_responses, artist_map):
        artist_map = self.create_featured_artists(release_responses, artist_map)
        release_map = self.create_releases(release_responses, artist_map)
        self.create_tags_and_taggings(release_responses, release_map)
        
    #
    
    def import_release(self, release_group_mbid):
        release_response = self.query_single_release(release_group_mbid)
        self.create_from_release_responses([release_response], ArtistMBIDMap())
    
    def import_artist(self, artist_mbid):
        artist_response = self.query_artist(artist_mbid)
        release_responses = self.query_all_releases(artist_response)
        
        artist_map = self.create_artists([artist_response])
        release_map = self.create_from_release_responses(release_responses, artist_map)
