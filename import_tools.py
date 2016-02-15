import re, os, urllib.request
import chromatography
from unidecode import unidecode
from colorsys import rgb_to_hsv

_punct_re = re.compile(r'[\t !:"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        result.extend(unidecode(word).split())
    return delim.join(result).lower()

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
        palette = sorted(palette, key=lambda p:rgb_to_hsv(p[0]/255, p[1]/255, p[2]/255)[2])
        os.remove(tempname)
        return [rgb_to_hex(color) for color in palette]
    except (chromatography.ChromatographyException, OSError):
        return [None, None, None]