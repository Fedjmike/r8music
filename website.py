import sqlite3
from contextlib import closing
from flask import Flask, render_template, g

from music_objects import Artist, Release, Track, ArtistNotFound, ReleaseNotFound
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
            
        db.commit()
        
    import_artist("Yung Lean")

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

@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html"), 404

@app.route("/")
def render_homepage():
    return render_template("layout.html")

def render_artists_index():
    artists = query_db("select * from artists")
    return render_template("artists_index.html", artists=artists)

@app.route("/<artist_slug>/<release_slug>")
def render_release(artist_slug, release_slug):
    try:
        release = Release.from_slugs(artist_slug, release_slug)
        return render_template("release.html", release=release)
        
    except (ArtistNotFound, ReleaseNotFound):
        return page_not_found("/%s/%s" % (artist_slug, release_slug))

@app.route("/<slug>/")
def render_artist(slug):
    if slug == "artists":
        return render_artists_index()

    try:
        artist = Artist.from_slug(slug)
        return render_template("artist.html", artist=artist)
        
    except ArtistNotFound:
        return page_not_found("/%s/" % (slug,))


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
