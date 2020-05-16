import re

from django.urls import re_path
from django.shortcuts import redirect

#

def fuzzy_groupby(iterable, threshold, key=lambda x: x):
    iterator = iter(iterable)
    item = None

    def group():
        nonlocal item
        group_continues = True
        
        while group_continues:
            yield item
            
            previous_item, item \
                = item, next(iterator, None)
            
            group_continues = item and abs(key(item) - key(previous_item)) <= threshold
    
    try:
        item = next(iterator)
        
        while item:
            yield key(item), group()
    
    except StopIteration:
        pass

#

def prefix_redirect_route(prefix, replacement, permanent=False):
    #The request object path includes a leading slash
    pattern = re.compile("^/" + prefix)
    replacement = "/" + replacement

    def redirect_view(request):
        new_url = re.sub(pattern, replacement, request.path)
        return redirect(new_url, permanent)

    return re_path(f"^{prefix}.*", redirect_view)
