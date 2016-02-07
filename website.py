from flask import Flask, render_template

import sqlite3
from contextlib import closing
from flask import g

app = Flask(__name__)

# Database

def connect_db():
    rv = sqlite3.connect("sample.db")
    rv.row_factory = sqlite3.Row
    return rv
    
def init_db():
    with closing(connect_db()) as db:
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        
        db.execute(
            "insert into artists (name, slug) values (?, ?)",
            ("My Bloody Valentine", "my-bloody-valentine")
        )
        
        mbv_id = 1
        releases = [
            ("Loveless", 1991, mbv_id, 'gay'),
            ("Isn't Anything", 1988, mbv_id, 'gay'),
            ("m b v", 2013, mbv_id, 'gay')
        ]
        
        for release in releases:
            db.execute(
                "insert into releases (title, year, artist_id, type) values (?, ?, ?, ?)",
                release
            )
        
        db.commit()

def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.db = connect_db()
        
    return g.db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

def query_db(query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

# 

@app.route("/")
@app.route("/<name>")
def render_release(name=None):
    print(query_db("select * from artists"))
    artist_releases = query_db("select * from releases")
    print(artist_releases)
    return render_template("release.html", name=name, releases=artist_releases)


# Nic messing around...
@app.route("/obj/artist/<name>")
def gen_artist_dom(name=None):
    from music_objects import Artist
    return str(Artist(name, 0000))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
