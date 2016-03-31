import re, os, urllib.request, requests
from chromatography import *
import wikipedia
import musicbrainzngs as mb
from collections import namedtuple
from itertools import combinations
from unidecode import unidecode
from colorsys import rgb_to_hls as bad_hls

_punct_re = re.compile(r'[\t !:"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        result.extend(unidecode(word).split())
    return delim.join(result).lower()

def get_wikipedia_summary(page):
    """page can be a title (string) or a wikipedia.WikipediaPage"""
    
    if isinstance(page, str):
        page = wikipedia.page(page, auto_suggest=True, redirect=True)
        
    response = requests.get("http://en.wikipedia.org/w/api.php", params=dict(
        action="query",
        format="json",
        prop="extracts",
        titles=page.title,
        exintro=""
    )).json()

    return response["query"]["pages"][page.pageid]["extract"]

def guess_wikipedia_page(artist_name):
    categories = ["musician", "band", "rapper"]
    
    try:
        page = wikipedia.page(artist_name)
        
        for link in page.links[:10]:
            if "disambiguation" in link:
                disambiguation_page = wikipedia.page(link)
                #Opening the disambiguation page will raise a DisambiguationError

        return page.title
        
    except wikipedia.exceptions.DisambiguationError as disambiguation:
        for name in disambiguation.options:
            if any(category in name for category in categories):
                return name
                
    except wikipedia.exceptions.PageError:
        pass
        
    return None
    
def get_wikipedia_urls(page_title):
    return "https://en.wikipedia.org/wiki/%s" % page_title, \
           "https://en.wikipedia.org/w/index.php?title=%s&action=edit" % page_title
    
def get_description(artist_name):
    page = guess_wikipedia_page(artist_name)
    return get_wikipedia_summary(page) if page else None

HLS = namedtuple("HLS", ["hue", "lightness", "saturation"])
rgb_to_hex = lambda color: "#%02x%02x%02x" % color
rgb_to_hls = lambda color: HLS(*bad_hls(*(c/255 for c in color)))
    
def hue_difference(pair):
    hues = [rgb_to_hls(c).hue for c in pair]
    diff = abs(hues[0] - hues[1])
    #Hue is a circular dimension. The most different colours are
    #those half way from each other
    return 1 - abs(0.5 - diff)
    
def valid_color(color):
    hue, lightness, saturation = rgb_to_hls(color)
    return saturation > 0.3 and lightness < 0.6 and lightness > 0.35

def get_palette(album_art_url):
    print("Getting palette...")
    try:
        tempname, _ = urllib.request.urlretrieve(album_art_url)
        palette = Chromatography(tempname).get_highlights(4, valid_color)
        os.remove(tempname)
        
        try:
            #Select the two colours with hues most different to each other
            most_different = max(combinations(palette, 2), key=hue_difference)
            #Put the brightest of these second
            most_different = sorted(most_different, key=lambda c: rgb_to_hls(c).lightness)
            #And then any other colours
            palette = most_different + [c for c in palette if c not in most_different]
            
        except:
            pass
            
        if len(palette) < 3:
            palette += [palette[0]] * (3 - len(palette))
        
        return [rgb_to_hex(color) for color in palette[:3]]
    
    except (NotEnoughValidPixels, BadColorMode):
        pass
    
    except (ChromatographyException, OSError):
        import traceback
        traceback.print_exc()
    
    return [None, None, None]

def search_artists(artist_name):
    mb.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
    r = mb.search_artists(artist=artist_name)
    artists = r['artist-list']
    return artists
