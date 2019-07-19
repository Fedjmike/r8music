import inspect
from collections import defaultdict

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

def query_and_collect(query, limits):
    """Collect reponses by querying a paginated resource.
       `query` is a function which takes limit and offset parameters and returns
       a list of responses. `limits` is the limit to be used for each query."""
    
    reponses = []
    offset = 0
    
    while True:
        response = query(limit=limits, offset=offset)
        
        reponses.extend(response)
        offset += limits
        
        if len(response) < limits:
            break
    
    return reponses
    
class MemoizedModule:
    """Replicates the functionality of a module and memoizes its functions.
       An instance can be treated just as the module it imitates.
       
       By memoizing the functions inside the module, no function will be run
       with the same arguments twice. If a particular function has side effects,
       it must be excluded from memoization."""
    
    def __init__(self, module, exceptions=[], storage=None, mock_only=False):
        def memoize_function(f, storage):
            def memoized(*args, **kwargs):
                #A hashable key for the storage dictionary
                args_key = (tuple(args), tuple(kwargs.items()))
                
                if args_key not in storage and not mock_only:
                    try:
                        storage[args_key] = (f(*args, **kwargs), None)
                        
                    except Exception as exception:
                        storage[args_key] = (None, exception)
                
                return_value, exception = storage[args_key]
                
                if return_value:
                    return return_value
                    
                else:
                    raise exception
                
            return memoized
        
        self.storage = storage if storage else defaultdict(dict)
        
        for name, value in inspect.getmembers(module):
            if name not in exceptions and inspect.isfunction(value):
                setattr(self, name, memoize_function(value, self.storage[name]))
                
            else:
                setattr(self, name, value)
