from django.contrib.staticfiles.storage import staticfiles_storage
from django import urls
from jinja2 import Environment

from r8music.profiles.urls import urlreversers as profile_urlreversers
from r8music.music.urls import urlreversers as music_urlreversers

def environment(**options):
    env = Environment(**options)
    
    env.globals.update({
        "static": staticfiles_storage.url,
        "url": urls.reverse
    })
    
    template_tools = profile_urlreversers + music_urlreversers
    env.globals.update({f.__name__: f for f in template_tools})

    return env
