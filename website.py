from flask import Flask, render_template, g
from contextlib import closing

from music_objects import Artist, Release, Track, User, NotFound
from import_artist import import_artist
from db import connect_db, close_db, get_db, query_db

app = Flask(__name__)

app.teardown_appcontext(close_db)

def init_db():
    with closing(connect_db()) as db:
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
            
        db.execute("insert into users (name) values (?)",
                   ("sam",))

        db.commit()
        
    import_artist("DJ Okawari")

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

def get_user():
    try:
        return User(1)
        
    except NotFound:
        return None

@app.route("/<artist_slug>/<release_slug>")
def render_release(artist_slug, release_slug):
    try:
        user = get_user()
        release = Release.from_slugs(artist_slug, release_slug)
        return render_template("release.html", release=release, user=user)
        
    except NotFound:
        return page_not_found("/%s/%s" % (artist_slug, release_slug))

@app.route("/<slug>/")
def render_artist(slug):
    if slug == "artists":
        return render_artists_index()

    try:
        user = get_user()
        artist = Artist.from_slug(slug)
        return render_template("artist.html", artist=artist, user=user)
        
    except NotFound:
        return page_not_found("/%s/" % (slug,))

@app.route("/rate/<int:release_id>/<int:rating>", methods=["POST"])
def change_rating(release_id, rating):
    user = get_user()
    
    db = get_db()
    db.execute("insert or replace into ratings (release_id, user_id, rating) values (?, ?, ?)",
                 (release_id, user._id, rating))
    db.commit()
    
    return "ok"

@app.route("/unrate/<int:release_id>", methods=["POST"])
def remove_rating(release_id):
    user = get_user()
    
    db = get_db()
    db.execute("delete from ratings where release_id=? and user_id=?",
                (release_id, user._id))
    db.commit()
    
    return "ok"

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
    #init_db()
    app.run(debug=True)
