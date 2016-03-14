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

#

template_tools = [friendly_datetime]

def add_template_tools(app):
    functions = {f.__name__: f for f in template_tools}
    app.jinja_env.globals.update(**functions)