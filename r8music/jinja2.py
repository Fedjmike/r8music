from datetime import datetime, timezone
from django.contrib.humanize.templatetags.humanize import naturaltime

from urllib.parse import urlencode

import json

from django.contrib.staticfiles.storage import staticfiles_storage
from django import urls
from django.contrib import messages

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

def full_datetime(then, tz=timezone.utc):
    return then.astimezone(tz).strftime("%A, %d %B %Y at %X")
    
def friendly_datetime(then, tz=timezone.utc):
    """Omit what is common between the given date and the current date"""
    
    then = then.astimezone(tz)
    now = datetime.now().astimezone(tz)

    #d is the day number, b is the short month name, Y is the year, X is the time
    format =      "%d %B %Y" if then.year != now.year \
             else "%d %B" if then.date() != now.date() \
             else "today at %X"
    return then.strftime(format)

def add_url_params(request, **new_params):
    params = dict(request.GET.items())
    params.update(new_params)
    return "?" + urlencode(params)

#

def environment(**options):
    env = Environment(**options)
    
    env.globals.update({
        "static": staticfiles_storage.url,
        "url": urls.reverse,
        "get_messages": messages.get_messages,
        "json_dumps": json.dumps,
        "relative_datetime": naturaltime
    })
    
    template_tools = [
        if_not_None, n_things, full_datetime, friendly_datetime, add_url_params,
        isinstance, tuple
    ]
    
    template_tools += profile_urlreversers + music_urlreversers
    
    env.globals.update({f.__name__: f for f in template_tools})
    
    return env
