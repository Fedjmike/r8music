import re, os, urllib.request, requests
import chromatography
import wikipedia
from unidecode import unidecode
from colorsys import rgb_to_hsv

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
    
def get_description(artist_name):
    categories = ['musician', 'band', 'rapper']
    try:
        page = wikipedia.page(artist_name)
        description = get_wikipedia_summary(page)
        for link in page.links:
            if 'disambiguation' in link:
                disambiguation_page = wikipedia.page(link)
                for l in disambiguation_page.links:
                    if any(word in name for word in categories):
                        return wikipedia.summary(name)
                break
        return description
    except wikipedia.exceptions.DisambiguationError as disambiguation:
        for name in disambiguation.options:
            if any(word in name for word in categories):
                return get_wikipedia_summary(name)
    except wikipedia.exceptions.PageError:
        pass
    return None

def rgb_to_hex(rgb):
    return '#%02x%02x%02x' % rgb


def valid_pixel(pixel):
    (h, s, v) = rgb_to_hsv(pixel[0]/255, pixel[1]/255, pixel[2]/255)
    if s > 0.3 and v > 0.4 and v < 0.95:
        return True
    return False

def get_palette(album_art_url):
    print("Getting palette...")
    try:
        tempname, _ = urllib.request.urlretrieve(album_art_url)
        c = chromatography.Chromatography(tempname)
        palette = c.get_highlights(3, valid_pixel)
        palette[:2] = sorted(palette[:2], key=lambda p:rgb_to_hsv(p[0]/255, p[1]/255, p[2]/255)[2])
        os.remove(tempname)
        return [rgb_to_hex(color) for color in palette]
    except (chromatography.ChromatographyException, OSError):
        return [None, None, None]
