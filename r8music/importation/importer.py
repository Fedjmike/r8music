import re, requests, wikipedia, musicbrainzngs, discogs_client
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

from r8music.music.models import Artist, ArtistExternalLink, generate_slug_tracked
from .models import ArtistMBLink, ArtistMBImportation, ArtistMBIDMap

class Importer:
    discogs_genre_blacklist = set([
        "Brass & Military", "Children's", "Folk, World, & Country",
        "Funk / Soul", "Non-Music", "Pop", "Stage & Screen"
    ])
    
    def __init__(self, requests=requests, musicbrainz=musicbrainzngs, wikipedia=wikipedia, discogs_client=discogs_client):
        self.requests = requests
        self.musicbrainz = musicbrainz
        self.wikipedia = wikipedia
        self.discogs = discogs_client.Client("r8music")
        
        self.musicbrainz.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
        
    def get_canonical_url(self, url):
        """Skip through redirects to get the "actual" URL"""
        return self.requests.get(url).url
    
    # Wikipedia
    
    wikipedia_url_pattern = re.compile("/wiki/(/?.*)")
    
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
            return None, None
            
        else:            
            #srcset is a list of images of different sizes, with scales
            thumbs = re.findall("(?:([^, ]*) ([\d.]*x))", image_link.img["srcset"])
            #Get the largest image
            thumb_url, scale = max(thumbs, key=lambda thumb_scale: thumb_scale[1])
            
            #Turn the URLs (which might be relative) into absolute URLs
            absolute_urls = [urljoin(wikipedia_page.url, url) for url in [image_url, thumb_url]]
            
            return absolute_urls
            
    def query_wikipedia(self, artist_name, wikipedia_url=None):        
        if wikipedia_url:
            title = self.wikipedia_url_pattern.search(wikipedia_url).group(1)
            wikipedia_page = self.wikipedia.page(title)
            
        else:
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
        def __init__(self, json, extra_links=None, description=None, image_url=None, image_thumb_url=None):
            self.json = json
            self.extra_links = extra_links
            self.description = description
            self.image_url = image_url
            self.image_thumb_url = image_thumb_url
        
    def query_artist(self, artist_mbid):
        artist_json = self.musicbrainz.get_artist_by_id(artist_mbid, includes=["url-rels"])["artist"]
        
        url_relations = artist_json.get("url-relation-list", [])
        candidates = (rel["target"] for rel in url_relations if rel["type"] == "wikipedia")
        wikipedia_url = next(candidates, None)
        
        guessed_wikipedia_url, description, images = \
            self.query_wikipedia(artist_json["name"], wikipedia_url)
        
        extra_links = [guessed_wikipedia_url]
        return self.ArtistResponse(artist_json, extra_links, description, *images)
        
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
    
    def find_discogs_url(self, url_relations):
        candidates = (rel["target"] for rel in url_relations if rel["type"] == "discogs")
        return next(candidates, None)
    
    def get_discogs_id(self, discogs_url):
        match = self.discogs_url_pattern.search(discogs_url)
        return match.group(3) if match else None
    
    def query_discogs_tags(self, discogs_id, is_master=False):
        release = (self.discogs.master if is_master else self.discogs.release)(discogs_id)
        tags = set(release.genres + release.styles) - self.discogs_genre_blacklist
        return tags
    
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
        
    def query_cover_art(self, release_json, release_group_json):
        art_urls = None
        
        #Prefer cover art specific to the release
        if release_json["cover-art-archive"]["artwork"] == "true":
            art_json = self.musicbrainz.get_image_list(release_json["id"])
            art_urls = self.select_cover_art(art_json)
            
        if not art_urls and release_group_json["cover-art-archive"]["artwork"] == "true":
            art_json = self.musicbrainz.get_release_group_image_list(release_group_json["id"])
            art_urls = self.select_cover_art(art_json)
            
        return art_urls
