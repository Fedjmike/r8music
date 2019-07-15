import re, requests, wikipedia, musicbrainzngs
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class Importer:
    def __init__(self, requests=requests, musicbrainz=musicbrainzngs, wikipedia=wikipedia):
        self.requests = requests
        self.musicbrainz = musicbrainz
        self.wikipedia = wikipedia
        
        self.musicbrainz.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
        
    def get_canonical_url(self, url):
        """Skip through redirects to get the "actual" URL"""
        return self.requests.get(url).url
    
    # Wikipedia
    
    wikipedia_url_pattern = re.compile("/wiki/(/?.*)")
    
    def guess_wikipedia_page(self, artist_name):
        music_categories = ["musician", "band", "rapper"]
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
            absolute_urls = [urljoin(wikipedia_page.url, url) for url in [thumb_url, image_url]]
            
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
