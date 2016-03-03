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
        
    def fits_in(self, color):
        distance = sq_distance(color, self.get_mean())
        fits = distance < self.range
        
        if fits:
            self.sum = [p+q for p, q in zip(color, self.sum)]
            self.frequency += 1
            self.range += distance/self.frequency
            
        return fits
        
    def get_mean(self):
        return tuple(int(part/self.frequency) for part in self.sum)


class Chromatography(object):
    def __init__(self, image_name):
        self.img = Image.open(image_name)
        self.scale_image()
        
    def scale_image(self):
        height, width = self.img.size
        target_area = 10000
        ratio = sqrt(height*width/target_area)
        self.img = self.img.resize((int(height/ratio), int(width/ratio)), Image.ANTIALIAS)

    def get_highlights(self, n=3, valid_color=None):
        if self.img.mode != "RGB":
            #B&W, no colours
            if self.img.mode in ["1", "L"]:
                raise BadColorMode("Can't extract colours from black and white image with colour mode " + self.img.mode)
                
            raise NotImplemented("Not implemented for images with colour mode " + self.img.mode)
        
        colors = [p for p in self.img.getdata() if valid_color(p)]
        
        if len(colors) == 0:
            raise NotEnoughValidPixels()
            
        clusters = []
        
        for color in colors:
            if not any(c.fits_in(color) for c in clusters):
                 clusters.append(Cluster(color))
                 
        top_clusters = sorted(clusters, key=lambda c: c.frequency, reverse=True)
        return [c.get_mean() for c in top_clusters[:n]]