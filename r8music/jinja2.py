from django.contrib.staticfiles.storage import staticfiles_storage
from django import urls
from jinja2 import Environment

def environment(**options):
    env = Environment(**options)
    
    env.globals.update({
        "static": staticfiles_storage.url,
        "url": urls.reverse
    })
    
    return env
