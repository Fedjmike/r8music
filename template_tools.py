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

def full_datetime(then):
    return then.strftime("%A, %d %B %Y at %X")
    
def friendly_datetime(then):
    """Omit what is common between the given date and the current date"""
    now = datetime.now()

    #d is the day number, b is the short month name, Y is the year, X is the time
    format =      "%d %B %Y at %X" if then.year != now.year \
             else "%d %B at %X" if then.date() != now.date() \
             else "today at %X"
    return then.strftime(format)

#Rating datasets

def sort_by_artist(releases):
    artist_then_date = lambda release: (release.get_artists()[0].name, release.date)
    return sorted(releases, key=artist_then_date)

def group_by_rating(ratings):
    """Turns [(release, rating)] into {rating: [release]}"""
    get_rated = lambda n: [release for release, rating in ratings if rating == n]
    return {n: get_rated(n) for n in range(1, 9)}
    
range_of = lambda list: range(min(list), max(list))
    
def get_release_year_counts(ratings):
    counts = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0, 0])
    
    for release, rating in ratings:
        year = int(release.date[:4])
        counts[year][rating-1] += 1

    #Fill in the missing years within the range
    for year in range_of(counts):
        if year not in counts:
            counts[year] = counts.default_factory()
    
    #[(year, (,,,,,,,,))]
    items = sorted(counts.items(), key=lambda kv: kv[0])
    #Transpose the table into [year], [(,,,,,,,,)]
    years, year_counts = zip(*items)
    
    #Return the year counts and year counts by rating
    #[year], [count], [[count]]
    return years, list(map(sum, year_counts)), list(zip(*year_counts))
    
def get_user_datasets(ratings):
    """Takes [(release, rating)] and gives various interesting datasets"""
    
    if not ratings:
        return None
    
    releases, _ = zip(*ratings)
    by_rating = group_by_rating(ratings)
    years, year_counts, year_counts_by_rating = get_release_year_counts(ratings)
    
    return {
        "ratingCounts": [len(releases) for releases in by_rating.values()],
        "releaseYearCounts": (years, year_counts),
        "releaseYearCountsByRating": (years, year_counts_by_rating),
    }
    
#

template_tools = [n_things, full_datetime, friendly_datetime, ("json_dumps", json.dumps), sort_by_artist, group_by_rating, get_user_datasets]

def add_template_tools(app):
    functions = dict((f.__name__, f) if hasattr(f, "__call__") else f for f in template_tools)
    app.jinja_env.globals.update(**functions)