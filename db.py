import sqlite3

from flask import g

def connect_db():
    db = sqlite3.connect("sample.db")
    db.row_factory = sqlite3.Row
    return db

def get_db():
    if not hasattr(g, 'db'):
        g.db = connect_db()
        
    return g.db

def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

def query_db(query, *args):
    """Queries the database and returns a list of dictionaries."""
    cur = get_db().execute(query, args)
    return cur.fetchall()
