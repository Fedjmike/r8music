import re, os, urllib.request, requests
from chromatography import Chromatography, ChromatographyException
import wikipedia
from collections import namedtuple
from unidecode import unidecode
from colorsys import rgb_to_hsv as bad_hsv

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

HSV = namedtuple("HSV", ["hue", "saturation", "value"])
rgb_to_hex = lambda color: "#%02x%02x%02x" % color
rgb_to_hsv = lambda color: HSV(*bad_hsv(*(c/255 for c in color)))

def valid_color(color):
    h, s, v = rgb_to_hsv(color)
    return s > 0.3 and v > 0.4 and v < 0.95

def get_palette(album_art_url):
    print("Getting palette...")
    try:
        tempname, _ = urllib.request.urlretrieve(album_art_url)
        palette = Chromatography(tempname).get_highlights(3, valid_color)
        os.remove(tempname)
        palette[:2] = sorted(palette[:2], key=lambda p:rgb_to_hsv(p).value)
        return [rgb_to_hex(color) for color in palette]
    except (ChromatographyException, OSError):
        return [None, None, None]
