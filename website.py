import os
from urllib.parse import urlparse, urljoin
import time

from flask import Flask, render_template, g, request, session, redirect, jsonify, url_for
from werkzeug import generate_password_hash
from contextlib import closing
from sqlite3 import IntegrityError

from music_objects import Artist, Release, Track, Rating, User, NotFound, UserAlreadyExists
from mb_api_import import import_artist
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
            
        db.commit()
        
    User.register("sam", "1", "sam.nipps@gmail.com")
    
    import_artist("DJ Okawari")

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return     test_url.scheme in ("http", "https") \
           and ref_url.netloc == test_url.netloc

def get_redirect_target():
    for target in request.values.get("next"), request.referrer:
        if not target:
            continue
            
        if is_safe_url(target):
            return target
    
def redirect_back():
    return redirect(get_redirect_target())

# 

@app.before_request
def before_request():
    g.start = time.time()

@app.after_request
def after_request(response):
    duration = (time.time() - g.start)*1000
    
    if duration > 5:
        print("Request took %d ms" % duration)
    
    return response

@app.errorhandler(404)
def page_not_found(what=None):
    return render_template("404.html", what=what), 404

@app.route("/")
def homepage():
    return render_template("layout.html")

@app.route("/artists")
def artists_index():
    artists = query_db("select * from artists")
    return render_template("artists_index.html", artists=artists)

@app.route("/users")
def users_index():
    users = query_db("select name from users")
    return render_template("users_index.html", users=users)

@app.route("/search", methods=["POST"])
def search_post():
    query = request.form["query"]
    #Redirect to a GET with the query in the path
    return redirect(url_for("search_results", query=query))

@app.route("/search/<query>", methods=["GET"])
def search_results(query=None):
    return render_template("search_results.html", search={"query": query, "results": []})

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
def release_page(artist_slug, release_slug):
    try:
        user = get_user()
        release = Release.from_slugs(artist_slug, release_slug)
        return render_template("release.html", release=release, user=user)
        
    except NotFound:
        return page_not_found("release")

#Routing is done later because /<slug>/ would override other routes
def artist_page(slug):
    try:
        user = get_user()
        artist = Artist.from_slug(slug)
        return render_template("artist.html", artist=artist, user=user)
        
    except NotFound:
        return page_not_found()

@app.route("/user/<slug>")
def user_page(slug):
    try:
        user = get_user()
        that_user = User.from_name(slug)
        return render_template("user.html", that_user=that_user, user=user)
        
    except NotFound:
        return page_not_found("user")

@app.route("/rate/<int:release_id>/<int:rating>", methods=["POST"])
def change_rating(release_id, rating):
    user_id = get_user_id()
    #todo error if no user

    Rating.set_rating(release_id, user_id, rating)

    rating_stats = Release(release_id).get_rating_stats()

    return jsonify(error=0,
                   ratingAverage=rating_stats.average,
                   ratingFrequency=rating_stats.frequency)

@app.route("/unrate/<int:release_id>", methods=["POST"])
def remove_rating(release_id):
    user_id = get_user_id()

    Rating.unset_rating(release_id, user_id)

    rating_stats = Release(release_id).get_rating_stats()

    return jsonify(error=0,
                   ratingAverage=rating_stats.average,
                   ratingFrequency=rating_stats.frequency)

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
        email = request.form["email"]
        
        if password != verify_password:
            return "LOL you typed your password wrong"
            
        #todo more restrictions, slugging
        elif len(name) < 4:
            return "Your username must be 4 characters or longer"
            
        try:
            if email == "":
                email = None
        
            user = User.register(name, password, email)
            #Automatically log them in
            set_user(user.name, user._id)
            
            return redirect_back()
            
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
                return redirect_back()
                
            else:
                return "Incorrect password for %s" % name
            
        except NotFound:
            #error
            return "User %s not found" % name

@app.route("/logout")
def logout():
    #todo check logged in

    session["user"] = None
    return redirect_back()

@app.route("/recover-password")
def recover_password():
    pass

#

if __name__ == "__main__":
    #init_db()
    app.add_url_rule("/<slug>/", view_func=artist_page)
    app.run(debug=True)
