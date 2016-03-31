from math import sqrt
from collections import namedtuple
from random import sample
from PIL import Image
from colorsys import rgb_to_hls as bad_hls

class ChromatographyException(Exception):
    pass

class NotEnoughValidPixels(ChromatographyException):
    pass

class BadColorMode(ChromatographyException):
    pass

class NotImplemented(ChromatographyException):
    pass

def sq_distance(l, r):
    #todo use a proper colour distance algorithm, use HSL
    return sum((a-b)**2 for a, b in zip(l, r))

class Cluster(object):
    def __init__(self, initial_color):
        self.frequency = 1
        self.sum = initial_color
        self.range = 800
        
    def fits_in(self, color):
        additional_frequency = 1
        
        """if isinstance(color, Cluster):
            additional_frequency = color.frequency
            color = color.get_mean()"""
    
        distance = sq_distance(color, self.get_mean())
        fits = distance < self.range
        
        if fits:
            self.sum = [p+q for p, q in zip(color, self.sum)]
            self.frequency += additional_frequency
            self.range += distance/self.frequency * additional_frequency
            
        return fits
        
    def get_mean(self):
        return tuple(int(part/self.frequency) for part in self.sum)


class Chromatography(object):
    def __init__(self, image_name):
        self.img = Image.open(image_name)
        
    def get_highlights(self, n=3, valid_color=None):
        if self.img.mode != "RGB":
            #B&W, no colours
            if self.img.mode in ["1", "L"]:
                raise BadColorMode("Can't extract colours from black and white image with colour mode " + self.img.mode)
                
            raise NotImplemented("Not implemented for images with colour mode " + self.img.mode)
        
        population = 5000
        colors = [p for p in self.img.getdata() if valid_color(p)]
        
        if len(colors) == 0:
            raise NotEnoughValidPixels()

        elif len(colors) > population:
            colors = sample(colors, population)
            
        print("%d valid colours" % len(colors))
        
        clusters = []
        
        for color in colors:
            if not any(c.fits_in(color) for c in clusters):
                 clusters.append(Cluster(color))
                 
        print("%d clusters" % len(clusters))
        
        """if len(clusters) > 30:
            new_clusters = []
                     
            for cluster in clusters:
                if not any(c.fits_in(cluster) for c in new_clusters):
                    new_clusters.append(cluster)
        
            print("%d final clusters" % len(new_clusters))
            clusters = new_clusters"""
        
        top_clusters = sorted(clusters, key=lambda c: c.frequency, reverse=True)
        print([(c.get_mean(), c.frequency) for c in top_clusters[:5]])
        return [c.get_mean() for c in top_clusters[:n]]