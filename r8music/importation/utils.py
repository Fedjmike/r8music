import inspect
from collections import defaultdict

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
