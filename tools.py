import re
from unidecode import unidecode

def flatten(lists):
    return [item for list in lists for item in list]

def chop_suffix(str, suffix):
    if not str.endswith(suffix):
        raise ValueError()
    
    return str[:-len(suffix)]

_punct_re = re.compile(r'[\t !:"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')

def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        result.extend(unidecode(word).split())
    return delim.join(result).lower()

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

#

def search_artists(artist_name):
    import musicbrainzngs as mb
    mb.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
    result = mb.search_artists(artist=artist_name)
    return result["artist-list"]
    
#

import requests
import wikipedia

def get_wikipedia_summary(title):
    response = requests.get("http://en.wikipedia.org/w/api.php", params=dict(
        action="query",
        format="json",
        prop="extracts",
        #todo request in bulk
        titles=title,
        exintro=""
    )).json()

    pages = list(response["query"]["pages"].values())
    return pages[0]["extract"]

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
        
    return None
    
def get_wikipedia_urls(page_title):
    return "https://en.wikipedia.org/wiki/%s" % page_title, \
           "https://en.wikipedia.org/w/index.php?title=%s&action=edit" % page_title
