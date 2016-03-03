import itertools, sqlite3
from functools import cmp_to_key, lru_cache
from datetime import datetime
from collections import namedtuple
from werkzeug import check_password_hash, generate_password_hash
from flask import g, url_for

from import_tools import slugify, get_wikipedia_urls, get_palette

# TODO: Modify query_db so "[i for (i,) in." is unnecessary.

class NotFound(Exception):
    pass
    
class AlreadyExists(Exception):
    pass
    
def now_isoformat():
    return datetime.now().isoformat()

def connect_db():
    db = sqlite3.connect("sample.db")
    db.row_factory = sqlite3.Row
    return db

def detect_collision(slug_candidate, db, table):
    result = db.execute('select count(*) from {} where slug=?'.format(table), (slug_candidate,)).fetchall()
    if result[0][0] > 0:
        return True
    return False

def avoid_collison(slug_candidate, db, table):
    if not detect_collision(slug_candidate, db, table):
        return slug_candidate

    for i in itertools.count(1):
        if not detect_collision(slug_candidate + "-" + str(i), db, table):
            return slug_candidate + "-" + str(i)

def generate_slug(text, db, table):
    slug_candidate = slugify(text)
    return avoid_collison(slug_candidate, db, table)
    
    
class Model:
    def __init__(self, connect_db=connect_db):
        self.db = connect_db()
        
    def close(self):
        self.db.close()

    def query(self, query, *args):
        return self.db.execute(query, args).fetchall()
        
    def query_unique(self, query, *args):
        result = self.query(query, *args)
        
        if len(result) == 0:
            raise NotFound()
            
        elif len(result) != 1:
            raise Exception("Result wasn't unique, '%s' with %s" % (query, str(args)))
            
        return result[0]
        
    def execute(self, query, *args):
        self.query(query, *args)
        self.db.commit()
        
    def insert(self, query, *args):
        cursor = self.db.cursor()
        cursor.execute(query, args)
        self.db.commit()
        return cursor.lastrowid
        
    #Artist
    
    Artist = namedtuple("Artist", ["id", "name", "slug", "releases", "get_image_url", "get_description", "get_wikipedia_urls"])
        
    def add_artist(self, name, description, incomplete=None):
        #Todo document "incomplete"
        
        slug = generate_slug(name, self.db, "artists")
        
        artist_id = self.insert("insert into artists (name, slug, incomplete) values (?, ?, ?)",
                                name, slug, incomplete)
                                
        self.insert("insert into artist_descriptions (artist_id, description) values (?, ?)",
                    artist_id, description)
                    
        return artist_id
        
    def _make_artist(self, row):
        def get_artist_wikipedia_urls():
            try:
                return get_wikipedia_urls(self.get_artist_link(row["id"], "wikipedia"))
            
            except NotFound:
                return None
        
    
        #Always need to know the releases, might as well get them eagerly
        return self.Artist(*row,
            releases=self.get_releases_by_artist(row["id"], row["slug"]),
            get_image_url=lambda: None,
            get_description=lambda: self.get_artist_description(row["id"]),
            get_wikipedia_urls=get_artist_wikipedia_urls
        )
        
    def get_artist(self, artist):
        """Retrieve artist info by id or by slug"""
        
        query = "select id, name, slug from artists where %s=?" % ("slug" if isinstance(artist, str) else "id")
        return self._make_artist(self.query_unique(query, artist))
        
    def get_release_artists(self, release_id, primary_artist_id=None):
        """Get all the artists who authored a release"""
        
        artists = [
            self._make_artist(row) for row in
            self.query("select id, name, slug from"
                       " (select artist_id from authorships where release_id=?)"
                       " join artists on artist_id = artists.id", release_id)
        ]
        
        if primary_artist_id:
            #Put the primary artist first
            ((index, primary_artist),) = [(i, a) for i, a in enumerate(artists) if a.id == primary_artist_id]
            return [primary_artist] + artists[:index] + artists[index+1:]
        
        return artists
        
    def get_artist_description(self, artist_id):
        return self.query_unique("select description from artist_descriptions where artist_id = (?)", artist_id)[0]

    def add_artist_link(self, artist_id, link_type, target):
        try:
            (link_type_id,) = self.query_unique("select id from link_types where type=?", link_type)
            
        except NotFound:
            link_type_id = self.insert("insert into link_types (type) values (?)", link_type)
            
        self.insert("insert into artist_links (artist_id, type_id, target)"
                    " values (?, ?, ?)", artist_id, link_type_id, target)

    def get_artist_link(self, artist_id, link_type):
        """link_type can either be the string that identifies a link, or its id"""
        
        @lru_cache(maxsize=128)
        def get_link_type_id(link_type):
            return self.query_unique("select id from link_types where type=?", link_type)[0]

        link_type_id = get_link_type_id(link_type) if isinstance(link_type, str) else link_type
    
        return self.query_unique("select target from artist_links"
                                 " where artist_id=? and type_id=?", artist_id, link_type_id)[0]

    #Release
    
    Release = namedtuple("Release", ["id", "title", "slug", "date", "release_type", "full_art_url", "thumb_art_url",
                                     "url", "get_tracks", "get_artists", "get_colors", "get_rating_stats"])
    
    #Handle selection/renaming for joins
    _release_columns = "release_id, title, slug, date, type, full_art_url, thumb_art_url"
    _release_columns_rename = "releases.id as release_id, title, slug, date, type, full_art_url, thumb_art_url"
    #todo rename the actual columns

    def add_release(self, title, date, type, full_art_url, thumb_art_url, mbid):
        slug = generate_slug(title, self.db, "releases")
        
        release_id = self.insert("insert into releases (title, slug, date, type, full_art_url, thumb_art_url)"
                                 " values (?, ?, ?, ?, ?, ?)", title, slug, date, type, full_art_url, thumb_art_url)

        self.add_palette(release_id, thumb_art_url)
        
        self.insert("insert into release_externals (release_id, mbid) values (?, ?)",
                    release_id, mbid)
                    
        return release_id
        
    def add_palette(self, release_id, image_url=None):
        palette = get_palette(image_url) if image_url else [None, None, None]
        self.insert("replace into release_colors (release_id, color1, color2, color3) values (?, ?, ?, ?)",
                    release_id, *palette)
                    
    def add_author(self, release_id, artist_id):
        self.insert("insert into authorships (release_id, artist_id) values (?, ?)",
                    release_id, artist_id)
    
    def _make_release(self, row, primary_artist_id=None, primary_artist_slug=None):
        release_id = row[0]
        release_slug = row[2]
        
        if not primary_artist_id:
            primary_artist_id, primary_artist_slug = \
                self.query_unique("select id, slug from"
                                  " (select artist_id from authorships where release_id=?)"
                                  " join artists on artist_id = artists.id limit 1", release_id)
        
        elif not primary_artist_slug:
            primary_artist_slug = self.query_unique("select slug from artists where id=?", primary_artist_id)
        
        return self.Release(*row,
            url=url_for("release_page", release_slug=release_slug, artist_slug=primary_artist_slug),
            get_artists=lambda: self.get_release_artists(release_id, primary_artist_id),
            get_colors=lambda: self.get_release_colors(release_id),
            get_tracks=lambda: self.get_release_tracks(release_id),
            get_rating_stats=lambda: self.get_release_rating_stats(release_id)
        )
        
    def get_releases_by_artist(self, artist_id, artist_slug=None):
        """artist_slug is optional but saves having to look it up"""
        
        return [
            self._make_release(row, artist_id, artist_slug) for row in
            self.query("select " + self._release_columns + " from"
                       " (select release_id from authorships where artist_id=?)"
                       " join releases on releases.id = release_id", artist_id)
        ]
        
    def get_releases_rated_by_user(self, user_id, rating=None):
        """Get all the releases rated by a user, and only those rated
           a certain value, if given"""
        return [
            self._make_release(row) for row in
            self.query("select " + self._release_columns + " from"
                       " (select release_id from ratings where user_id=?"
                       + (" and rating=?)" if rating else ")") +
                       " join releases on releases.id = release_id", user_id, rating)
        ]
        
    def get_release(self, artist_slug, release_slug):
        #Select the artist and release rows with the right slugs
        # (first, to make the join small)
        #Join them using authorships
        artist_id, *row = \
            self.query_unique("select artist_id, " + self._release_columns + " from"
                              " (select artists.id as artist_id from artists where artists.slug=?)"
                              " natural join authorships natural join"
                              " (select " + self._release_columns_rename + " from releases where releases.slug=?)",
                              artist_slug, release_slug)

        return self._make_release(row, artist_id, artist_slug)
        
    def get_release_colors(self, release_id):
        return self.query_unique("select color1, color2, color3 from release_colors"
                                 " where release_id=?", release_id)
        
    #Rating
    
    RatingStats = namedtuple("RatingStats", ["average", "frequency"])
        
    def set_release_rating(self, release_id, user_id, rating):
        self.execute("replace into ratings (release_id, user_id, rating, creation)"
                     " values (?, ?, ?, ?)", release_id, user_id, rating, now_isoformat())

    def unset_release_rating(self, release_id, user_id):
        # TODO: Error if no rating present?
        self.execute("delete from ratings"
                     " where release_id=? and user_id=?", release_id, user_id)
        
    def get_release_rating_stats(self, release_id):
        try:
            ratings = [r for (r,) in self.query("select rating from ratings where release_id=?", release_id)]
            frequency = len(ratings)
            average = sum(ratings) / frequency
            return self.RatingStats(average=average, frequency=frequency)
            
        except ZeroDivisionError:
            return self.RatingStats(average=None, frequency=0)
        
    #Track
    
    Track = namedtuple("Track", ["title", "runtime"])
    
    def add_track(self, release_id, title, position, runtime):
        slug = generate_slug(title, self.db, "tracks")
                    
        self.insert("insert into tracks (release_id, title, slug, position, runtime) values (?, ?, ?, ?, ?)",
                    release_id, title, slug, position, runtime)

    def get_release_tracks(self, release_id):
        #todo sort by position
        return [
            self.Track(title,
                       "%d:%02d" % (runtime//60000, (runtime/1000) % 60) if runtime else None)
            for title, runtime
            in self.query("select title, runtime from tracks where release_id=?", release_id)
        ]

    #User
    
    User = namedtuple("User", ["id", "name", "creation", "ratings", "get_releases_rated"])
    
    def _make_user(self, _id, name, creation, ratings):
        return self.User(_id, name, creation, ratings,
            get_releases_rated=lambda rating=None: self.get_releases_rated_by_user(_id, rating)
        )
    
    def get_user(self, user):
        """Get user by id or by slug"""
        
        query = "select id, name, creation from users where name=?" if isinstance(user, str) \
                else "select id, name, creation from users where id=?"
        user_id, name, creation = self.query_unique(query, user)
        
        ratings = dict(self.query("select release_id, rating from ratings"
                                  " where ratings.user_id=?", user_id))
                                
        return self._make_user(user_id, name, creation, ratings)
        
    def register_user(self, name, password, email=None, fullname=None):
        """Try to add a new user to the database.
           Perhaps counterintuitively, for security hashing the password is
           delayed until this function. Better that you accidentally hash
           twice than hash zero times and store the password as plaintext."""
    
        if self.query("select id from users where name=?", name):
            raise AlreadyExists()
            
        creation = now_isoformat()
        user_id = self.insert("insert into users (name, pw_hash, email, fullname, creation) values (?, ?, ?, ?, ?)",
                              name, generate_password_hash(password), email, fullname, creation)
                       
        return self._make_user(user_id, name, creation, {})
    
    def user_pw_hash_matches(self, given_password, user_slug):
        """For security, the hash is never stored anywhere except the databse.
           For added security, it doesn't even leave this function."""
        user_id, db_hash = self.query_unique("select id, pw_hash from users where name=?", user_slug)
        matches = check_password_hash(db_hash, given_password)
        return (matches, user_id if matches else None)
