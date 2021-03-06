import inspect
from collections import defaultdict

from r8music.music.models import ReleaseType

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
    
def musicbrainz_url(mbid, artist=False):
    return "//musicbrainz.org/%s/%s" % ("artist" if artist else "release", mbid)
    
def get_release_type_from_mb_str(release_type_str):
    try:
        return {
            "Album": ReleaseType.ALBUM,
            "Single": ReleaseType.SINGLE,
            "EP": ReleaseType.EP,
            "Broadcast": ReleaseType.BROADCAST,
            "Other": ReleaseType.OTHER,
            "Compilation": ReleaseType.COMPILATION,
            "Soundtrack": ReleaseType.SOUNDTRACK,
            "Spokenword": ReleaseType.SPOKENWORD,
            "Interview": ReleaseType.INTERVIEW,
            "Audiobook": ReleaseType.AUDIOBOOK,
            "Audio drama": ReleaseType.AUDIO_DRAMA,
            "Live": ReleaseType.LIVE,
            "Remix": ReleaseType.REMIX,
            "DJ-mix": ReleaseType.DJ_MIX,
            "Mixtape/Street": ReleaseType.MIXTAPE_STREET,
            "Demo": ReleaseType.DEMO
        }[release_type_str]
    
    except KeyError:
        raise ValueError("Unknown release type string: " + release_type_str)
    
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
                        
                    #pylint:disable=broad-except
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
