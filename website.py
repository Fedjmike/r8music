import os

from flask import Flask, render_template, g, request, session, redirect, jsonify
from werkzeug import generate_password_hash
from contextlib import closing
from sqlite3 import IntegrityError

from music_objects import Artist, Release, Track, User, NotFound, UserAlreadyExists
from import_artist import import_artist
from db import connect_db, close_db, get_db, query_db

app = Flask(__name__)
#Used to encrypt cookies and session data. Change this to a constant to avoid
#losing your session when the server restarts
app.secret_key = os.urandom(24)

app.teardown_appcontext(close_db)

def init_db():
    with closing(connect_db()) as db:
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
            
        db.execute("insert into users (name, pw_hash) values (?, ?)",
                   ("sam", generate_password_hash("1")))

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

def render_users_index():
    users = query_db("select name from users")
    return render_template("users_index.html", users=users)

def get_user_id():
    try:
        return session["user"]["id"]
        
    except (TypeError, KeyError):
        return None
        
def get_user():
    try:
        return User(session["user"]["id"])
        
    except (NotFound, TypeError, KeyError):
        return None

def set_user(name, _id):
    session["user"] = {"name": name, "id": _id}

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
        
    elif slug == "users":
        return render_users_index()

    try:
        user = get_user()
        artist = Artist.from_slug(slug)
        return render_template("artist.html", artist=artist, user=user)
        
    except NotFound:
        return page_not_found("/%s/" % (slug,))

@app.route("/user/<name>")
def render_user(name):
    try:
        user = get_user()
        that_user = User.from_name(name)
        return render_template("user.html", that_user=that_user, user=user)
        
    except NotFound:
        return page_not_found("/%s/" % (name,))

@app.route("/rate/<int:release_id>/<int:rating>", methods=["POST"])
def change_rating(release_id, rating):
    user_id = get_user_id()
    #todo error if no user
    
    db = get_db()
    
    try:
        db.execute("insert into ratings (release_id, user_id, rating) values (?, ?, ?)",
                   (release_id, user_id, rating))
        #If the above didn't raise an error, the release wasn't already rated
        db.execute("update rating_totals set frequency = frequency + 1, sum = sum + ? where release_id=?",
                   (rating, release_id,))

    #Rating already present, replace
    except IntegrityError:
        #todo transactions
        ((old_rating,),) = query_db("select rating from ratings where release_id=? and user_id=?",
                                    (release_id, user_id))
        
        db.execute("replace into ratings (release_id, user_id, rating) values (?, ?, ?)",
                   (release_id, user_id, rating))
        db.execute("update rating_totals set sum = sum + ? where release_id=?",
                   (rating - old_rating, release_id))
        
    db.commit()
    
    ((sum, frequency,),) = query_db("select sum, frequency from rating_totals where release_id=?",
                                    (release_id,))
    
    return jsonify(error=0, ratingSum=sum, ratingFrequency=frequency)

@app.route("/unrate/<int:release_id>", methods=["POST"])
def remove_rating(release_id):
    user_id = get_user_id()
    
    db = get_db()

    try:
        ((old_rating,),) = query_db("select rating from ratings where release_id=? and user_id=?",
                                    (release_id, user_id))
    
    #No rating present
    except ValueError:
        #TODO: User attempted to unrate something not rated. Should we just say
        #it succeeded, so that their client gets updated to what is (and was
        #already) the case?
        return jsonify(error=1)
        
    db.execute("delete from ratings where release_id=? and user_id=?",
               (release_id, user_id))
    db.execute("update rating_totals set frequency = frequency - 1, sum = sum - ? where release_id=?",
               (old_rating, release_id))
    db.commit()
    
    ((sum, frequency,),) = query_db("select sum, frequency from rating_totals where release_id=?",
                                    (release_id,))
    
    return jsonify(error=0, ratingSum=sum, ratingFrequency=frequency)

@app.route("/register", methods=["GET", "POST"])
def register():
    #todo check not logged in

    if request.method == "GET":
        #todo https
        return render_template("register.html")
        
    else:
        name = request.form["username"]
        password = request.form["password"]
        verify_password = request.form["verify-password"]
        
        if password != verify_password:
            return "LOL you typed your password wrong"
            
        #todo more restrictions, slugging
        elif len(name) < 4:
            return "Your username must be 4 characters or longer"
            
        try:
            user = User.register(name, password)
            #Automatically log them in
            set_user(user.name, user._id)
            
            #todo redirect to previous page
            return redirect("/")
            
        except UserAlreadyExists:
            #error
            return "Username %s already taken" % name

@app.route("/login", methods=["GET", "POST"])
def login():
    #todo check not logged in

    if request.method == "GET":
        #todo https
        return render_template("login.html")
        
    else:
        name = request.form["username"]
        password = request.form["password"]
        
        try:
            _id = User.id_from_name(name)
            
            if User.pw_hash_matches(password, _id):
                set_user(name, _id)
                #todo redirect to previous page
                return redirect("/")
                
            else:
                return "Incorrect password for %s" % name
            
        except NotFound:
            #error
            return "User %s not found" % name

@app.route("/logout")
def logout():
    #todo check logged in

    session["user"] = None
    return redirect("/")
    
    
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
