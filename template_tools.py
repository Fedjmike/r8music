from datetime import datetime
from collections import defaultdict, namedtuple
from itertools import groupby
import arrow

from tools import transpose, sortable_date, fuzzy_groupby, group_by_key

def if_not_None(x, fallback=""):
    return x if x is not None else fallback

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
    format =      "%d %B %Y" if then.year != now.year \
             else "%d %B" if then.date() != now.date() \
             else "today at %X"
    return then.strftime(format)

def relative_datetime(then):
    return then.humanize()

#Actions

ActionGroup = namedtuple("ActionGroup", ["user", "actions"])

def action_groups(actions):
    from model import ActionType
    
    threshold = 60*60 #1h in seconds
    
    overriding_actions = defaultdict(lambda: [])
    overriding_actions.update({
        ActionType.listen: [ActionType.rate],
        ActionType.list: [ActionType.rate, ActionType.listen]
    })
    
    def group_by_object_and_omit(actions):
        for _, actions_on_object in groupby(actions, key=lambda action: action.object.id):
            actions_on_object = list(actions_on_object)
            
            def not_overridden(action):
                #Omit this action if an overriding action is present in this group
                return not any(other_action.type in overriding_actions[action.type]
                               for other_action in actions_on_object)
                
            yield from filter(not_overridden, actions_on_object)
            
    def group_by_user_and_time(actions):
        actions = group_by_key(actions, key=lambda action: action.user.id)

        for user, actions_by_user in groupby(actions, key=lambda action: action.user):
            for _, close_actions in fuzzy_groupby(actions_by_user,
                                                  key=lambda action: action.creation.timestamp,
                                                  threshold=threshold):
                close_actions = list(group_by_object_and_omit(close_actions))
                yield ActionGroup(user, close_actions)

    action_groups = group_by_user_and_time(actions)

    return sorted(action_groups, key=lambda ag: -ag.actions[0].creation.timestamp)

#Rating datasets

def sort_by_artist(releases):
    artist_then_date = lambda release: (release.get_artists()[0].name, release.date)
    return sorted(releases, key=artist_then_date)

def group_by_rating(ratings):
    """Turns [(release, rating)] into {rating: [release]}"""
    get_rated = lambda n: [release for release, rating in ratings if rating == n]
    return {n: get_rated(n) for n in range(1, 9)}

def group_by_year(releases):
    year = lambda release: release.date[:4]
    releases = sorted(releases, key=lambda r: sortable_date(r.date))
    releases_by_year = {y: list(r) for y, r in groupby(releases, year)}
    years = sorted(releases_by_year.keys(), reverse=True)

    return years, releases_by_year
    
range_of = lambda list: range(min(list), max(list)) if list else []
    
def get_release_year_counts(ratings=[], listened_unrated=[]):
    #Split by year then rating (first element = listened unrated)
    counts = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0, 0, 0])
    
    for release, rating in ratings + [(r, 0) for r in listened_unrated]:
        year = int(release.date[:4])
        counts[year][rating] += 1

    #Fill in the missing years within the range
    for year in range_of(counts):
        if year not in counts:
            counts[year] = counts.default_factory()
    
    #[(year, (,,,,,,,,))] sorted by year
    items = sorted(counts.items(), key=lambda kv: kv[0])
    #Transpose the table into [year], [(,,,,,,,,)]
    years, year_counts = transpose(items, rows=2)
    
    #Return the year counts and year counts by rating
    #[year], [count], [[count]]
    return years, list(map(sum, year_counts)), list(transpose(year_counts, rows=9))
    
def get_user_datasets(ratings=[], listened_unrated=[]):
    """Takes [(release, rating)] and [release] and gives various interesting datasets"""
    
    releases, _ = transpose(ratings, rows=2)
    by_rating = group_by_rating(ratings)
    years, year_counts, year_counts_by_rating = get_release_year_counts(ratings, listened_unrated)
    
    return {
        "ratingCounts": [len(releases) for releases in by_rating.values()],
        "releaseYearCounts": (years, year_counts),
        "releaseYearCountsByRating": (years, year_counts_by_rating),
    }
    
#

from flask import url_for

def url_for_user(user, **kwargs):
    return url_for("user_page", slug=user.name, **kwargs)
    
def url_for_release(artist, release):
    try:
        return url_for("release_page", artist_slug=artist, release_slug=release)
        
    #Outside Flask app context
    except RuntimeError:
        return None
    
#

import json

template_tools = [
    if_not_None, n_things,
    full_datetime, friendly_datetime, relative_datetime,
    action_groups, sort_by_artist, group_by_year, group_by_rating,
    get_user_datasets,
    url_for_user,
    isinstance, tuple, ("json_dumps", json.dumps)
]

def add_template_tools(app):
    functions = dict((f.__name__, f) if hasattr(f, "__call__") else f for f in template_tools)
    app.jinja_env.globals.update(**functions)