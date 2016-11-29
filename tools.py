#Iterables

from itertools import chain

def flatten(lists):
    return [item for list in lists for item in list]
    
def uniq(iter, key=lambda x: x):
    seen = set()
    
    for item in iter:
        item_key = key(item)
        
        if item_key not in seen:
            seen.add(item_key)
            yield item

def transpose(table, rows):
    return zip(*table) if len(table) != 0 else [[]]*rows

def dict_values(dict, keys):
    return [dict[key] if key in dict else None
            for key in keys]

def dict_subset(dict, keys):
    return {key: dict[key] for key in keys if key in dict}

class fuzzy_groupby(object):
    def __init__(self, iterable, key=lambda x: x, threshold=0):
        self.key = key
        self.close_enough = lambda x, y: abs(key(x) - key(y)) <= threshold
        
        self.it = iter(iterable)
        self.target = self.current = object()

    def __iter__(self):
        return self

    def __next__(self):
        try: # Fails during first iteration
            while self.close_enough(self.current, self.target):
                self.target = next(self.it)

        except (TypeError, AttributeError):
            self.target = next(self.it)

        self.current = self.target
        return (self.key(self.target), self._grouper(self.target))

    def _grouper(self, current):
        while self.target and self.close_enough(current, self.target):
            yield self.target
            self.target = next(self.it, None)

def group_by_key(items, key):
    """Takes an unordered list, returns list with elements with identical keys grouped together"""
    d = dict()

    for item in items:
        try:
            d[key(item)].append(item)

        except KeyError:
            d[key(item)] = [item]

    return chain(*[d[k] for k in d])

#Strings

import re
from unidecode import unidecode

def chop_suffix(str, suffix):
    if not str.endswith(suffix):
        raise ValueError()
    
    return str[:-len(suffix)]

try:
    import editdistance
    edit_distance = editdistance.eval
    
except ImportError:
    def edit_distance(s1, s2):
        """From http://stackoverflow.com/a/32558749"""
        
        if len(s1) > len(s2):
            s1, s2 = s2, s1

        distances = range(len(s1) + 1)
        for i2, c2 in enumerate(s2):
            distances_ = [i2+1]
            for i1, c1 in enumerate(s1):
                if c1 == c2:
                    distances_.append(distances[i1])
                else:
                    distances_.append(1 + min((distances[i1], distances[i1 + 1], distances_[-1])))
            distances = distances_
        return distances[-1]

_punct_re = re.compile(r'[\t !:"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        result.extend(unidecode(word).split())
    return delim.join(result).lower()

#Date/time

import arrow

def sortable_date(date):
    """Accepts dates of the form YYYY, YYYY-MM or YYYY-MM-DD and extends them to a full date."""
    
    #Year only
    if len(date) == 4:
        return date + "-12-31"
        
    #Year and  month
    elif len(date) == 7:
        return arrow.get(date + '-01').replace(months=+1, days=-1).format('YYYY-MM-DD')
        
    else:
        return date

#Yo dawg I heard you like decorating so I made some decorators to 
#decorate your decorators into decorators

def disguise(f, disguise):
    f.__name__ = disguise.__name__

def basic_decorator(decorator):
    """Turns a given function (`decorator`) into a decorator. This function
    takes one argument (`f`), which is the function to be decorated.
    
    `f` can be called with any additional arguments that the decorator wants
    to provide, which will be given to `f` before the arguments given by the
    caller of the decorated `f`.
    
    some_value = 1
    
    @basic_decorator
    def my_decorator(f):
        ... things involving f(some_value) ...
        
    @my_decorator
    def f(some_value, arg):
        print(some_value, arg)
    
    #Prints "1 2"
    f(2)"""

    def decorated_decorator(f):
        def decorated_f(*f_args, **f_kwargs):
            call_f = lambda *extra_f_args: f(*(extra_f_args + f_args), **f_kwargs)
            disguise(call_f, f)
            return decorator(call_f)
        
        disguise(decorated_f, f)
        return decorated_f
    
    disguise(decorated_decorator, decorator)
    return decorated_decorator

@basic_decorator
def decorator_with_args(decorator):
    """Extending basic_decorator, here the given `decorator` function takes
    its own arguments after the `f` that is to be decorated.
    
    @decorator_with_args
    def maporator(f, *args):
        for arg in args:
            f(arg)
            
    @maporator(1, 2, 3)
    def f(n, m):
        print(n+m)
    
    #Prints "3\n4\n5"
    f(2)"""

    @basic_decorator
    def decorated_decorator(f):
        return decorator(f)
        
    return decorated_decorator

#Profiling

from cProfile import Profile
from time import perf_counter

@basic_decorator
def execution_time(f):
    start = perf_counter()                     
    result = f()
    duration = (perf_counter() - start)*1000
    
    if duration > 1:
        print("%.2f" % duration, "ms spent in", f.__name__)
        
    return result

@basic_decorator
def profiled(f):
    try:
        profile = Profile()
        result = profile.runcall(f)
        return result
    
    finally:
        profile.print_stats(sort="cumtime")

#Wikipedia

def search_mb(query, query_type='artist'):
    import musicbrainzngs as mb
    mb.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")

    if query_type == 'artist':
        result = mb.search_artists(artist=query)
        return result["artist-list"]

    else:
        result = mb.search_release_groups(releasegroup=query)
        return result['release-group-list']
    
#

import re, urllib.parse, requests, wikipedia
from bs4 import BeautifulSoup

class WikipediaPageNotFound(Exception):
    pass

def _wikipedia_query(titles, **args):
    response = requests.get("http://en.wikipedia.org/w/api.php", params=dict(
        action="query",
        format="json",
        titles=urllib.parse.unquote(titles),
        **args
    )).json()
    
    return list(response["query"]["pages"].values())

def get_wikipedia_summary(title):
    try:
        pages = _wikipedia_query(
            prop="extracts",
            titles=title,
            exintro=""
        )
        
        return pages[0]["extract"]
        
    except KeyError as e:
        print("get_wikipedia_summary error:", repr(e), pages)
        return ""

def get_wikipedia_image(title):
    url, _ = get_wikipedia_urls(title)
    html = BeautifulSoup(requests.get(url).text)
    
    try:
        image_link = html.select(".infobox a.image")[0]
        
        full_href = image_link["href"]
        full_url = "https://en.wikipedia.org" + full_href if full_href.startswith("/wiki/") else full_href
        
        #srcset is a list of images of different sizes, with scales
        thumbs = re.findall("(?:([^, ]*) ([\d.]*x))", image_link.img["srcset"])
        #Get the largest image, by the scale
        thumb_url, scale = max(thumbs, key=lambda thumb_scale: thumb_scale[1])
        
        return thumb_url, full_url
        
    except (IndexError, KeyError):
        return None

def guess_wikipedia_page(artist_name):
    categories = ["musician", "band", "rapper"]
    
    try:
        page = wikipedia.page(artist_name)
        
        for link in page.links[:10]:
            if "disambiguation" in link:
                #Opening a disambiguation page will raise a DisambiguationError
                wikipedia.page(link)

        return page.title
        
    except wikipedia.exceptions.DisambiguationError as disambiguation:
        for name in disambiguation.options:
            if any(category in name for category in categories):
                return name
                
    except wikipedia.exceptions.PageError:
        pass
        
    raise(WikipediaPageNotFound)
    
def get_wikipedia_urls(page_title):
    if page_title is None:
        return None
        
    return "https://en.wikipedia.org/wiki/%s" % page_title, \
           "https://en.wikipedia.org/w/index.php?title=%s&action=edit" % page_title

# Avatars

from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import HTTPError
from imghdr import what

valid_domains = ["i.imgur.com", "my.mixtape.moe"]
max_size = 322322 # 322 KB in bytes
allowed_types = ["jpeg", "png", "gif"]

class AvatarException(Exception):
    pass

class DomainNotWhitelisted(AvatarException):
    pass

class TooBig(AvatarException):
    pass

class ImageError(AvatarException):
    pass

def validate_avatar(avatar_url):
    if urlparse(avatar_url).netloc not in valid_domains:
        raise DomainNotWhitelisted("Error: " + avatar_url + " is not a whitelisted domain." +\
                                   " Allowed domains: " + ", ".join(valid_domains))

    try:
        r = urlopen(avatar_url)

    except HTTPError:
        raise ImageError("Couldn't download the image for validation")

    filesize = int(r.info().get("Content-Length"))
    if filesize > max_size:
        raise TooBig("File size " + str(filesize//1000) + " kB exceeds max size " \
                     + str(max_size//1000) + " kB")

    _type = what('', h=r.read())

    if _type not in allowed_types:
        raise ImageError("File must be a valid jpg, png or gif")

# Rankings

from math import sqrt, log, exp

# From http://www.johndcook.com/blog/python_phi_inverse/
def rational_approximation(t):
    # Abramowitz and Stegun formula 26.2.23.
    # The absolute value of the error should be less than 4.5 e-4.
    c = [2.515517, 0.802853, 0.010328]
    d = [1.432788, 0.189269, 0.001308]
    numerator = (c[2]*t + c[1])*t + c[0]
    denominator = ((d[2]*t + d[1])*t + d[0])*t + 1.0
    return t - numerator / denominator


def normal_CDF_inverse(p):
    assert p > 0.0 and p < 1
    # See article above for explanation of this section.
    if p < 0.5:
        # F^-1(p) = - G^-1(p)
        return -rational_approximation( sqrt(-2.0*log(p)) )
    else:
        # F^-1(p) = G^-1(1-p)
        return rational_approximation( sqrt(-2.0*log(1.0-p)) )

Z = normal_CDF_inverse(1 - (1 - 0.95) / 2)

def binomial_score(likes, totes):
    r = likes/totes

    return (r + Z**2/(2*totes) - Z*sqrt((r*(1-r) + Z**2/(4*totes))/totes))/(1 + Z**2/totes)

def sigmoid(x):
    return 1/(1+exp(-(x-3)))

sigmoid_map = {i: sigmoid(i) for i in range(1, 8)}