import os, time, requests, multiprocessing.pool, sqlite3
from urllib.parse import urlparse, urljoin

from flask import Flask, render_template, g, request, session, redirect, jsonify, url_for
from contextlib import closing
from bs4 import BeautifulSoup

from model import Model, User, connect_db, NotFound, AlreadyExists, ActionType
from mb_api_import import import_artist, MBID
from template_tools import add_template_tools
from tools import basic_decorator, decorator_with_args, search_artists

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

app.teardown_appcontext(lambda exception: model().close())

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
            
    return "/"
    
def redirect_back():
    return redirect(get_redirect_target())

def encode_query_str(query):
    #Not a bijection, ' ' and '+' both go to '+'.
    #TODO replace '+' with '%2B', without url_for HTTP encoding the percent itself
    return "+".join(query.split(" "))
    
def decode_query_str(query):
    return query.replace("+", " ")
    
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

@app.route("/artists")
def artists_index():
    artists = model().query("select * from artists")
    return render_template("artists_index.html", artists=artists)

@app.route("/users")
def users_index():
    users = model().query("select name from users")
    return render_template("users_index.html", users=users)

default_search_args = {"type": "artists"}
search_args = default_search_args.keys()

def only_valid_search_args(args, filter_out=False):
    return {k: v for k, v in args.items() if k in search_args}

@app.route("/search", methods=["GET", "POST"])
def search():
    if request.method == "GET":
        return render_template("search.html", search={"args": default_search_args})
        
    else:
        query = encode_query_str(request.form["query"])
        args = only_valid_search_args(request.form)
        #Only args different from the default
        args = {k: v for k, v in args.items() if v != default_search_args[k]}
        
        #Redirect to a GET with the query in the path
        return redirect(url_for("search_results", query=query, **args))

@app.route("/search/<query>", methods=["GET"])
@app.route("/search/", methods=["GET"])
def search_results(query=None):
    if not query:
        return redirect(url_for("search"))

    query = decode_query_str(query)
    args = default_search_args.copy()
    args.update(only_valid_search_args(request.args))
    
    results = model().search(query, **args)
    return render_template("search_results.html",
            search={"query": query, "args": args, "results": results})

def get_user():
    try:
        return model().get_user(session["user"]["id"])
    
    except (KeyError, TypeError):
        return None

def set_user(user):
    #Can't store the user obj directly as methods can't be seralized
    session["user"] = {"id": user.id, "name": user.name}

@basic_decorator
def with_user(view):
    """A decorator for pages that (can) use the logged in User, but
       do not *require* authentication."""
    request.user = get_user()
    return view()

@basic_decorator
def needs_auth(view):
    """A decorator for pages that require authentication"""
    request.user = get_user()
    
    if not request.user:
        #todo
        #todo send JSON for some pages (e.g. rating, with UI info)
        return "Not authenticated", 403
    
    else:
        return view()
    
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
    
    if action in [ActionType.rate, ActionType.unrate]:
        try:
            rating = request.values["rating"] if action == ActionType.rate else None
            model().set_rating(request.user.id, release_id, rating)
            return rating_stats()
            
        #No rating field sent
        except KeyError:
            return jsonify(error=1), 400
    
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
        if "artist-id" in request.form:
            #todo ajax progress
            artist_id = MBID(request.form["artist-id"])
            app_pool.apply_async(import_artist, (artist_id,))
            return redirect_back()
            
        else:
            query = encode_query_str(request.form["artist-name"])
            return redirect(url_for("add_artist_search_results", query=query))

@app.route("/add-artist-search/<query>", methods=["GET"])
@app.route("/add-artist-search/", methods=["GET"])
@needs_auth
def add_artist_search_results(query=None):
    if not query:
        return redirect(url_for("add_artist"))
        
    query = decode_query_str(query)
    artists = search_artists(query)
    return render_template("add_artist_search_results.html", artists=artists, query=query)

@app.route("/")
@with_user
def homepage():
    return render_template("activity_feed.html")

@app.route("/user/<slug>", methods=["GET", "POST"])
@with_user
def user_page(slug):
    try:
        that_user = model().get_user(slug)
        
    except NotFound:
        return      (jsonify(error=1), 404) if request.method == "POST" \
               else page_not_found(what="user")
    
    if request.values:
        try:
            action = {
                "follow": model().follow,
                "unfollow": model().unfollow
            }[request.values["action"]]
            
            action(request.user.id, that_user.id)
        
        except (KeyError, sqlite3.Error):
            return jsonify(error=1), 400
    
    if request.method == "POST":
        return jsonify(error=0)
        
    elif request.values:
        #Redirect so that the user doesn't stay on the action URL
        return redirect(url_for("user_page", slug=slug))
        
    else:
        return render_template("user.html", that_user=that_user, user=request.user)

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

@decorator_with_args
def sanitize_new_password(view, new_password, again):
    if new_password != again:
        return "LOL you typed your password wrong"
        
    return view()
    
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
        
        @sanitize_new_password(password, verify_password)
        def register(email=email):
            #todo more restrictions, slugging
            if len(name) < 4:
                return "Your username must be 4 characters or longer"
                
            try:
                if email == "":
                    email = None
                    
                user = model().register_user(name, password, email)
                #Automatically log them in
                set_user(user)
                
                return redirect_back()
                
            except AlreadyExists:
                #error
                return "Username %s already taken" % name
        
        return register()

@decorator_with_args
def confirm_password(view, user, password):
    """Runs a view, if the credentials given are correct, otherwise
    displays an error. `user` may be an id or name. Passes the
    corresponding user object into the given view."""
    try:
        matches, user = model().user_pw_hash_matches(user, password)
        
        if matches:
            return view(user)

        else:
            return "Incorrect password for '%s'" % user.name
            
    except NotFound:
        #error
        return "User '%s' not found" % user.name

@app.route("/set-password", methods=["GET", "POST"])
@needs_auth
def set_password():
    if request.method == "GET":
        #todo https
        return render_template("set_password.html")
        
    else:
        password = request.form["password"]
        new_password = request.form["new-password"]
        verify_new_password = request.form["verify-new-password"]
        
        @sanitize_new_password(new_password, verify_new_password)
        @confirm_password(request.user.id, password)
        def set_password(user):
            model().set_user_pw(user.id, new_password)
            return redirect_back()
            
        return set_password()
        
@app.route("/settings", methods=["GET", "POST"])
@needs_auth
def user_settings():
    if request.method == "GET":
        return render_template("settings.html", user=request.user)
    
    else:
        email, timezone = (request.form[key] if key in request.form else None
                           for key in ["email", "timezone"])
        
        #Allow the user to set email to an empty string
        if email is not None:
            model().set_user_email(request.user.id, email)
            
        if timezone:
            model().set_user_timezone(request.user.id, timezone)
        
        return redirect(url_for("user_settings"))
        
@app.route("/rating-descriptions", methods=["GET", "POST"])
@needs_auth
def rating_descriptions():
    try:
        rating, description = (request.form[key] for key in ["rating", "description"])
        
        rating = int(rating)
        description = BeautifulSoup(description).get_text().strip()
        
        if description == "":
            description = None
        
        model().set_user_rating_description(request.user.id, rating, description)
        
        description = model().get_user_rating_descriptions(request.user.id)[rating]
        return jsonify(error=0, description=description)
    
    except KeyError:
        return jsonify(error=1), 400
        
@app.route("/login", methods=["GET", "POST"])
def login():
    #todo check not logged in

    if request.method == "GET":
        #todo https
        return render_template("login.html")
        
    else:
        name = request.form["username"]
        password = request.form["password"]

        @confirm_password(name, password)
        def login(user):
            set_user(user)
            return redirect_back()
            
        return login()

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
    
    add_template_tools(app)
    
    app.add_url_rule("/<slug>", view_func=artist_page)
    app.run(debug=True)
