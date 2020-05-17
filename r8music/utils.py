import re
from collections import defaultdict

from django.urls import re_path
from django.shortcuts import redirect

#

def uniqify(iterable, key=lambda x: x):
    return list({key(item): item for item in iterable}.values())

def mode_items(iterable, key=lambda x: x):
    """Select the mode item(s) (i.e. the most common ones) from an iterable,
       as identified by the given key."""
    
    items_grouped_by_key = defaultdict(lambda: [])
    
    for item in iterable:
        items_grouped_by_key[key(item)].append(item)
        
    groups = items_grouped_by_key.values()
    largest_group_size = max(map(len, groups), default=0)
    
    return [
        item
        for group in groups if len(group) == largest_group_size
        for item in group
    ]

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
