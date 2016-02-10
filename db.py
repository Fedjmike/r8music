import sqlite3
from contextlib import closing

from flask import g

def connect_db():
    rv = sqlite3.connect("sample.db")
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    if not hasattr(g, 'db'):
        g.db = connect_db()
        
    return g.db

def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

def query_db(query, args=(), one=False, db=None):
    """Queries the database and returns a list of dictionaries."""
    if not db:
        db = get_db()
    cur = db.execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv
