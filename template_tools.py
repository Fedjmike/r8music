from datetime import datetime
from collections import defaultdict

def friendly_datetime(then):
    """Omit what is common between the given date and the current date"""
    now = datetime.now()

    #d is the day number, b is the short month name, Y is the year, X is the time
    format =      "%d %b %Y, %X" if then.year != now.year \
             else "%d %b, %X" if then.date() != now.date() \
             else "%X"
    return then.strftime(format)

def group_by_rating(ratings):
    """Take a list of tuples of (release, rating)"""

    release_name = lambda release: release.get_artists()[0].name
    get_rated = lambda n: [release for release, rating in ratings if rating == n]
    
    return {n: sorted(get_rated(n), key=release_name) for n in range(1, 9)}
    
#

template_tools = [friendly_datetime, group_by_rating]

def add_template_tools(app):
    functions = {f.__name__: f for f in template_tools}
    app.jinja_env.globals.update(**functions)