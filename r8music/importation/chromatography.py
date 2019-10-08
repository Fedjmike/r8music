from math import sqrt
from collections import namedtuple
from PIL import Image

class ChromatographyException(Exception):
    pass

class NotEnoughValidPixels(ChromatographyException):
    pass

class BadColorMode(ChromatographyException):
    pass

class NotImplemented(ChromatographyException):
    pass

def sq_distance(l, r):
    return sum((a-b)**2 for a, b in zip(l, r))

class Cluster(object):
    def __init__(self, initial_color):
        self.frequency = 1
        self.sum = initial_color
        self.range = 800
        
    def try_add(self, color):
        distance = sq_distance(color, self.get_mean())
        fits_in = distance < self.range
        
        if fits_in:
            self.sum = [p+q for p, q in zip(color, self.sum)]
            self.frequency += 1
            self.range += distance/self.frequency
            
        return fits_in
        
    def get_mean(self):
        return tuple(int(part/self.frequency) for part in self.sum)


class Chromatography(object):
    sample_size = 10000
    
    def __init__(self, image_name):
        self.img = Image.open(image_name)
        self.scale_image()
        
        if self.img.mode in ["1", "L"]:
            raise BadColorMode("Can't extract colours from black and white image with colour mode " + self.img.mode)
            
        elif self.img.mode != "RGB":
            raise NotImplemented("Not implemented for images with colour mode " + self.img.mode)
        
    def scale_image(self):
        height, width = self.img.size
        ratio = sqrt(height*width/self.sample_size)
        self.img = self.img.resize((int(height/ratio), int(width/ratio)), Image.ANTIALIAS)

    def get_highlights(self, n=3, valid_color=None):
        colors = [p for p in self.img.getdata() if valid_color(p)]
        
        if len(colors) == 0:
            raise NotEnoughValidPixels()
            
        clusters = []
        
        for color in colors:
            if not any(c.try_add(color) for c in clusters):
                 clusters.append(Cluster(color))
                 
        top_clusters = sorted(clusters, key=lambda c: c.frequency, reverse=True)
        return [c.get_mean() for c in top_clusters[:n]]

#

import os
from itertools import combinations
from colorsys import rgb_to_hls as bad_hls
from urllib.request import urlretrieve

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
    try:
        tempname, _ = urlretrieve(album_art_url)
        palette = Chromatography(tempname).get_highlights(3, valid_color)
        os.remove(tempname)
        
        try:
            #Select the two colours with hues most different to each other
            most_different = max(combinations(palette, 2), key=hue_difference)
            
        except ValueError:
            pass
            
        else:
            #Put the brightest of these second
            most_different = sorted(most_different, key=lambda c: rgb_to_hls(c).lightness)
            #And then any other colours
            palette = most_different + [c for c in palette if c not in most_different]
            
        if len(palette) < 3:
            palette += [palette[0]] * (3 - len(palette))
        
        return [rgb_to_hex(color) for color in palette]
    
    except (NotEnoughValidPixels, BadColorMode):
        pass
    
    except (ChromatographyException, OSError):
        import traceback
        traceback.print_exc()
    
    return [None, None, None]
