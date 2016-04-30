import os, time, requests, multiprocessing.pool, sqlite3
from urllib.parse import urlparse, urljoin

from flask import Flask, render_template, g, request, session, redirect, jsonify, url_for, flash
from contextlib import closing
from bs4 import BeautifulSoup

from model import Model, User, connect_db, NotFound, AlreadyExists, ActionType, UserType, RatingStats
from mb_api_import import import_artist, MBID
from template_tools import add_template_tools
from tools import dict_values, dict_subset, basic_decorator, decorator_with_args, search_artists

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

def get_user():
    try:
        return model().get_user(session["user"]["id"])
    
    except (KeyError, TypeError):
        return None

def set_user(user):
    #Can't store the user obj directly as methods can't be seralized
    session["user"] = {"id": user.id, "name": user.name}

@app.before_request
def with_user():
    request.user = get_user()

@basic_decorator
def needs_auth(view):
    """Display an error if not authenticated"""
    
    if not request.user:
        #todo
        #todo send JSON for some pages (e.g. rating, with UI info)
        return "Not authenticated", 401
    
    else:
        return view()

@decorator_with_args
@needs_auth
def needs_priv(view, allowed=["admin"]):
    if request.user.type.name not in allowed:
        #todo
        return "Not authorised", 403
        
    return view()

def from_ajax():
    return request.method == "POST"

@decorator_with_args
def handle_not_found(f, what=None, form=False):
    try:
        return f()
    
    except NotFound:
        return      (jsonify(error=1), 404) if from_ajax() and not form \
               else page_not_found(what=what)
    
# Views

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
        return render_template("form.html", form="search", search={"args": default_search_args})
        
    else:
        query = encode_query_str(request.form["query"])
        args = only_valid_search_args(request.form)
        #Only args different from the default
        args = {k: v for k, v in args.items() if v != default_search_args[k]}
        
        #Redirect to a GET with the query in the path
        return redirect(url_for("search_results", query=query, **args))

@app.route("/search/<query>")
@app.route("/search/")
def search_results(query=None):
    if not query:
        return redirect(url_for("search"))

    query = decode_query_str(query)
    args = default_search_args.copy()
    args.update(only_valid_search_args(request.args))
    
    results = model().search(query, **args)
    return render_template("search_results.html",
            search={"query": query, "args": args, "results": results})

@app.route("/<artist_slug>/<release_slug>", methods=["GET", "POST"])
@app.route("/<artist_slug>/<release_slug>/<any(reviews):tab>")
@handle_not_found(what="release")
def release_page(artist_slug, release_slug, tab=None):
    release = model().get_release(artist_slug, release_slug)

    if request.method == "GET":
        return render_template("release.html", release=release, tab=tab, user=request.user)
        
    else:
        return release_post(release.id)

@app.route("/release/<int:release_id>", methods=["POST"])
@handle_not_found(what="release")
@needs_auth
def release_post(release_id):
    def rating_stats():
        rating_stats = RatingStats(model().get_ratings(release_id))
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
    
@app.route("/<artist_slug>/<release_slug>/edit", methods=["GET", "POST"])
@handle_not_found(what="release", form=True)
@needs_priv()
def edit_release(artist_slug, release_slug):
    release = model().get_release(artist_slug, release_slug)
        
    if request.method == "POST":
        try:
            colors = [request.values["color-%d" % n] for n in [1, 2, 3]]
            model().set_palette(release.id, colors)
            
        except KeyError:
            #todo
            return "Invalid palette", 400
        
    return render_template("edit_release.html", release=release)

#Routing is done later because /<slug>/ would override other routes
@handle_not_found()
def artist_page(slug):
    artist = model().get_artist(slug)
    return render_template("artist.html", artist=artist, user=request.user)

@app.route("/add-artist", methods=["GET", "POST"])
@needs_auth
def add_artist():
    if request.method == "GET":
        return render_template("add_artist.html")
        
    else:
        if "artist-id" in request.form:
            #todo ajax progress
            artist_id = MBID(request.form["artist-id"])
            app_pool.apply_async(import_artist, (artist_id,))
            return redirect(url_for("artists_index"))
            
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
def homepage():
    return render_template("activity_feed.html")

@app.route("/user/<slug>", methods=["GET", "POST"])
@app.route("/user/<slug>/<any(rated, 'listened-unrated', activity):tab>")
@handle_not_found(what="user")
def user_page(slug, tab="rated"):
    that_user = model().get_user(slug)
    
    if request.values:
        try:
            action = {
                "follow": model().follow,
                "unfollow": model().unfollow
            }[request.values["action"]]
            
            action(request.user.id, that_user.id)
        
        except (KeyError, sqlite3.Error):
            return jsonify(error=1), 400
    
    if from_ajax():
        return jsonify(error=0)
        
    elif request.values:
        #Redirect so that the user doesn't stay on the action URL / form submission
        return redirect(url_for("user_page", slug=slug))
        
    else:
        return render_template("user.html", that_user=that_user, tab=tab, user=request.user)

@decorator_with_args
def confirm_recaptcha(view, recaptcha_response, remote_addr, error_view):
    response = requests.post(
        "https://www.google.com/recaptcha/api/siteverify",
        data={
            "secret": g_recaptcha_secret,
            "response": recaptcha_response,
            "remoteip": remote_addr
        }
    ).json()

    if "error-codes" in response:
        if response["error-codes"] == ["missing-input-response"]:
            pass #User error
        
        else:
            flash("Recaptcha error: " + str(response["error-codes"]), "recaptcha-error")
            return error()
    
    if not response["success"]:
        flash("Sorry, you appear to be a robot. Try again?", "recaptcha-error")
        return error_view()
        
    else:
        return view()

@decorator_with_args
def sanitize_new_password(view, new_password, again, error_view):
    if new_password != again:
        flash("The passwords didn't match", "verify-new-password-error")
        return error_view()
        
    elif len(new_password) < 6:
        flash("Your password must be 6 characters or longer", "new-password-error")
        return error_view()
        
    return view()
    
@decorator_with_args
def sanitize_new_username(view, name, error_view):
    try:
        if len(name) < 4:
            flash("Your username must be 4 characters or longer", "username-error")
            return error_view()
            
        elif model().user_exists(name):
            raise AlreadyExists()
            
        #Catch an AlreadyExists if the view raises one (although it shouldn't)
        return view()
            
    except AlreadyExists:
        flash("'%s' is already taken" % name, "username-error")
        return error_view()
    
@app.route("/register", methods=["GET", "POST"])
def register():
    #todo check not logged in

    if request.method == "GET":
        #todo https
        return render_template("form.html", form="register")
        
    else:
        name, password, verify_password, email, recaptcha_response = dict_values(request.values,
            ["username", "new-password", "verify-new-password", "email", "g-recaptcha-response"])
        
        def error():
            return render_template("form.html", form="register",
                form_prefill=dict_subset(request.values, ["username", "email"]))
        
        #todo more restrictions, slugging
        @sanitize_new_password(password, verify_password, error)
        @sanitize_new_username(name, error)
        @confirm_recaptcha(recaptcha_response, request.remote_addr, error)
        def register(email=email if email else None):
            user = model().register_user(name, password, email)
            #Automatically log them in
            set_user(user)
            
            flash("Welcome to r8music", "success")
            return redirect_back()
        
        return register()

@decorator_with_args
def confirm_password(view, user, password, error_view):
    """Runs a view, if the credentials given are correct, otherwise
    displays an error. `user` may be an id or name. Passes the
    corresponding user object into the given view."""
    try:
        matches, user = model().user_pw_hash_matches(user, password)
        
        if matches:
            return view(user)

        else:
            flash("Incorrect password for '%s'" % user.name, "password-error")
            return error_view()
            
    except NotFound:
        flash("User '%s' not found" % user, "username-error")
        return error_view()

@app.route("/set-password", methods=["GET", "POST"])
@needs_auth
def set_password():
    if request.method == "GET":
        #todo https
        return render_template("form.html", form="set_pw")
        
    else:
        password, new_password, verify_new_password = dict_values(request.values,
            ["password", "new-password", "verify-new-password"])
        
        def error():
            return render_template("form.html", form="set_pw")
        
        @sanitize_new_password(new_password, verify_new_password, error)
        @confirm_password(request.user.id, password, error)
        def set_password(user):
            model().set_user_pw(user.id, new_password)
            flash("Password changed", "success")
            return redirect_back()
            
        return set_password()
        
@app.route("/settings", methods=["GET", "POST"])
@needs_auth
def user_settings():
    if request.method == "GET":
        return render_template("settings.html", user=request.user)
    
    else:
        email, timezone = dict_values(request.values, ["email", "timezone"])
        
        #Allow the user to set email to an empty string
        if email is not None:
            model().set_user_email(request.user.id, email)
            
        if timezone:
            model().set_user_timezone(request.user.id, timezone)
        
        flash("Settings saved", "success")
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
        return render_template("form.html", form="login")
        
    else:
        name = request.form["username"]
        password = request.form["password"]
        
        def error():
            return render_template("form.html", form="login")

        @confirm_password(name, password, error)
        def login(user):
            set_user(user)
            flash("Logged in", "success")
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
