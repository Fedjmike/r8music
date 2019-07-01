from datetime import datetime
from pytz import timezone
from django.contrib.humanize.templatetags.humanize import naturaltime

import json

from django.contrib.staticfiles.storage import staticfiles_storage
from django import urls
from jinja2 import Environment

from r8music.profiles.urls import urlreversers as profile_urlreversers
from r8music.music.urls import urlreversers as music_urlreversers

def if_not_None(x, fallback=""):
    return x if x is not None else fallback

def pluralise(noun):
    vowels = ["a", "e", "i", "o", "u"]
    inflection =      "es" if noun.endswith("o") and noun[-2] not in vowels \
                 else "es" if any(noun.endswith(suffix) for suffix in ["s", "z", "sh", "ch"]) \
                 else "ies" if noun.endswith("y") \
                 else "s"
    return noun + inflection
    
def n_things(n, noun):
    return "%d %s" % (n, noun if n == 1 else pluralise(noun))

def full_datetime(then, timezone_name):
    return then.astimezone(timezone(timezone_name)).strftime("%A, %d %B %Y at %X")
    
def friendly_datetime(then):
    """Omit what is common between the given date and the current date"""
    now = datetime.now()

    #d is the day number, b is the short month name, Y is the year, X is the time
    format =      "%d %B %Y" if then.year != now.year \
             else "%d %B" if then.date() != now.date() \
             else "today at %X"
    return then.strftime(format)

#

def environment(**options):
    env = Environment(**options)
    
    env.globals.update({
        "static": staticfiles_storage.url,
        "url": urls.reverse,
        "json_dumps": json.dumps,
        "relative_datetime": naturaltime
    })
    
    template_tools = [
        if_not_None, n_things, full_datetime, friendly_datetime, isinstance, tuple
    ]
    
    template_tools += profile_urlreversers + music_urlreversers
    
    env.globals.update({f.__name__: f for f in template_tools})
    
    return env
