from datetime import datetime
from collections import defaultdict
import json

def pluralize(noun):
    vowels = ["a", "e", "i", "o", "u"]
    inflection =      "es" if noun.endswith("o") and noun[-2] not in vowels \
                 else "es" if any(noun.endswith(suffix) for suffix in ["s", "z", "sh", "ch"]) \
                 else "ies" if noun.endswith("y") \
                 else "s"
    return noun + inflection
    
def n_things(n, noun):
    return "%d %s" % (n, noun if n == 1 else pluralize(noun))
    
def friendly_datetime(then):
    """Omit what is common between the given date and the current date"""
    now = datetime.now()

    #d is the day number, b is the short month name, Y is the year, X is the time
    format =      "%d %b %Y, %X" if then.year != now.year \
             else "%d %b, %X" if then.date() != now.date() \
             else "%X"
    return then.strftime(format)

def group_by_rating(ratings):
    """Takes a list of tuples of (release, rating)"""

    release_key = lambda release: (release.get_artists()[0].name, release.date)
    get_rated = lambda n: [release for release, rating in ratings if rating == n]
    
    return {n: sorted(get_rated(n), key=release_key) for n in range(1, 9)}
    
def get_release_year_counts(ratings):
    """Take a list of tuples of (release, rating)"""
    counts = defaultdict(lambda: 0)
    
    for release, _ in ratings:
        year = int(release.date[:4])
        counts[year] += 1
        
    return counts
    
def get_user_datasets(ratings):
    return {
        "ratingCounts": [len(group) for group in group_by_rating(ratings).values()]
    }
    
#

template_tools = [n_things, friendly_datetime, ("json_dumps", json.dumps), group_by_rating, get_user_datasets]

def add_template_tools(app):
    functions = dict((f.__name__, f) if hasattr(f, "__call__") else f for f in template_tools)
    app.jinja_env.globals.update(**functions)