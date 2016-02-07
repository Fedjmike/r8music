import sqlite3
from contextlib import closing
from flask import Flask, render_template, g

from music_objects import Artist, Release, Track
from import_artist import import_artist

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
        
        import_artist("My Bloody Valentine")
        
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
def render_homepage():
    return "home sweet home"
    
@app.route("/<artist_slug>/<release_slug>")
def render_release(artist_slug, release_slug):
    try:
        artist = Artist.from_slug(artist_slug)
        release = Release.from_slug(artist, release_slug)
        return render_template("release.html", release=release)
        
    #todo ArtistNotFound, ReleaseNotFound
    except ValueError:
        return "404"

@app.route("/<slug>/")
def render_artist(slug=None):
    try:
        artist = Artist.from_slug(slug)
        return render_template("artist.html", artist_name=artist.name, releases=artist.releases)
        
    except ValueError:
        return "404"


# Nic messing around...
#@app.route("/<artist>")
def artist_dom_from_slug(artist=None):
    return str(Artist.from_slug(artist))

@app.route("/a/<int:_id>")
def artist_dom_from_id(_id=None):
    return str(Artist(_id))

@app.route("/<artist>/<release>")
def release_dom_from_slugs(artist, release):
    artist = Artist.from_slug(artist)
    return str(Release.from_slug(artist, release))

@app.route("/a/<int:artist_id>/r/<int:release_id>")
def release_dom_from_id(artist_id, release_id):
    artist = Artist(artist_id)
    return str(Release(artist, release_id))



if __name__ == "__main__":
    init_db()
    app.run(debug=True)
