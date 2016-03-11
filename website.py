import os, time, requests, multiprocessing.pool
from collections import namedtuple
from urllib.parse import urlparse, urljoin
from datetime import datetime

from flask import Flask, render_template, g, request, session, redirect, jsonify, url_for
from werkzeug import generate_password_hash
from contextlib import closing
from sqlite3 import IntegrityError

from model import Model, connect_db, NotFound, AlreadyExists, ActionType
from mb_api_import import import_artist

g_recaptcha_secret = "todo config"

app = Flask(__name__)
#Used to encrypt cookies and session data. Change this to a constant to avoid
#losing your session when the server restarts
app.secret_key = os.urandom(24)

app_pool = None

def model():
    if not hasattr(g, "model"):
        g.model = Model()
        
    return g.model

@app.teardown_appcontext
def close_model(exception):
    model().close()

def init_db():
    return

    with closing(connect_db()) as db:
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
            
        db.commit()
        
    Model().register_user("sam", "1", "sam.nipps@gmail")
    
    import_artist("DJ Okawari")

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return     test_url.scheme in ("http", "https") \
           and ref_url.netloc == test_url.netloc

def get_redirect_target():
    for target in request.values.get("next"), request.referrer:
        if target and is_safe_url(target):
            return target
    
def redirect_back():
    return redirect(get_redirect_target())

def friendly_datetime(then):
    """Omit what is common between the given date and the current date"""
    now = datetime.now()

    #d is the day number, b is the short month name, Y is the year, X is the time
    format =      "%d %b %Y, %X" if then.year != now.year \
             else "%d %b, %X" if then.date() != now.date() \
             else "%X"
    return then.strftime(format)

# 

@app.before_request
def before_request():
    request.start = time.time()

@app.after_request
def after_request(response):
    duration = (time.time() - request.start)*1000
    
    if duration > 5:
        print("Request took %d ms" % duration)
    
    return response

@app.errorhandler(404)
def page_not_found(e=None, what=None):
    return render_template("404.html", what=what), 404

@app.route("/")
def homepage():
    return render_template("layout.html")

@app.route("/artists")
def artists_index():
    artists = model().query("select * from artists")
    return render_template("artists_index.html", artists=artists)

@app.route("/users")
def users_index():
    users = model().query("select name from users")
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
        return model().get_user(session["user"]["id"])
        
    except (NotFound, TypeError, KeyError):
        return None

def set_user(name, _id):
    session["user"] = {"name": name, "id": _id}

def with_user(f):
    """A decorator for pages that (can) use the logged in User, but
       do not *require* authentication."""
    def decorated(*args, **kwargs):
        request.user = get_user()
        return f(*args, **kwargs)
        
    #Make the name appear the same, for routing and debugging
    decorated.__name__ = f.__name__
    return decorated

UserID = namedtuple("UserID", ["id"])

def needs_auth(f):
    """A decorator for pages that require authentication"""
    def decorated(*args, **kwargs):
        request.user = UserID(get_user_id())
        
        if request.user.id == None:
            #todo
            #todo send JSON for some pages (e.g. rating, with UI info)
            return "Not authenticated", 403
        
        else:
            return f(*args, **kwargs)
        
    decorated.__name__ = f.__name__
    return decorated
    
@app.route("/<artist_slug>/<release_slug>", methods=["GET", "POST"])
@with_user
def release_page(artist_slug, release_slug):
    try:
        release = model().get_release(artist_slug, release_slug)
        
    except NotFound:
        return page_not_found(what="release")

    if request.method == "GET":
        return render_template("release.html", release=release, user=request.user)
        
    else:
        return release_post(release.id)

@app.route("/release/<int:release_id>", methods=["POST"])
@needs_auth
def release_post(release_id):
    def rating_stats():
        rating_stats = model().get_rating_stats(release_id)
        return jsonify(error=0,
                       ratingAverage=rating_stats.average,
                       ratingFrequency=rating_stats.frequency)

    try:
        action = ActionType[request.values["action"]]
        
    except KeyError:
        return jsonify(error=1), 400 #HTTPStatus.BAD_REQUEST
    
    if action == ActionType.rate:
        try:
            model().set_rating(request.user.id, release_id, request.values["rating"])
            return rating_stats()
            
        #No rating field sent
        except (KeyError):
            return jsonify(error=1), 400
        
    elif action == ActionType.unrate:
        model().unset_rating(request.user.id, release_id)
        return rating_stats()
    
    else:
        model().add_action(request.user.id, release_id, action)
        return jsonify(error=0)

#Routing is done later because /<slug>/ would override other routes
@with_user
def artist_page(slug):
    try:
        artist = model().get_artist(slug)
        return render_template("artist.html", artist=artist, user=request.user)
        
    except NotFound:
        return page_not_found()

@app.route("/artists/add", methods=["GET", "POST"])
@needs_auth
def add_artist():
    if request.method == "GET":
        return render_template("add_artist.html")
        
    else:
        #todo allow mbid
        #todo ajax progress
        artist_name = request.form["artist-name"]
        app_pool.apply_async(import_artist, (artist_name,))
        return redirect_back()
    
@app.route("/user/<slug>")
@with_user
def user_page(slug):
    try:
        that_user = model().get_user(slug)
        return render_template("user.html", that_user=that_user, user=request.user)
        
    except NotFound:
        return page_not_found(what="user")

def failed_recaptcha(recaptcha_response, remote_addr):
    response = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={
            "secret": g_recaptcha_secret,
            "response": recaptcha_response,
            "remoteip": remote_addr
        }
    ).json()

    #Incorrect use of the API, not captcha failure
    if "error-codes" in response:
        raise Exception(response["error-codes"])
    
    return not response["success"]

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
        recaptcha_response = request.form["g-recaptcha-response"]
        
        if failed_recaptcha(recaptcha_response, request.remote_addr):
            return "Sorry, you appear to be a robot"
        
        if password != verify_password:
            return "LOL you typed your password wrong"
            
        #todo more restrictions, slugging
        elif len(name) < 4:
            return "Your username must be 4 characters or longer"
            
        try:
            if email == "":
                email = None
        
            user = model().register_user(name, password, email)
            #Automatically log them in
            set_user(user.name, user.id)
            
            return redirect_back()
            
        except AlreadyExists:
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
            matches, user_id = model().user_pw_hash_matches(password, name)
            
            if matches:
                set_user(name, user_id)
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
    app_pool = multiprocessing.pool.ThreadPool(processes=4)
    init_db()
    app.add_url_rule("/<slug>", view_func=artist_page)
    app.jinja_env.globals.update(friendly_datetime=friendly_datetime)
    app.run(debug=True)
