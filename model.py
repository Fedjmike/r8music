from functools import cmp_to_key
from collections import namedtuple
from db import query_db, get_db
from werkzeug import check_password_hash, generate_password_hash

# TODO: Modify query_db so "[i for (i,) in." is unnecessary.

class NotFound(Exception):
    pass
    
class AlreadyExists(Exception):
    pass
    
def now_isoformat():
    from datetime import datetime
    return datetime.now().isoformat()

class Model:
    def query(self, query, *args):
        return query_db(query, *args)
        
    def query_unique(self, query, *args):
        result = self.query(query, *args)
        
        if len(result) == 0:
            raise NotFound()
            
        elif len(result) != 1:
            raise Exception("Result wasn't unique, '%s' with %s" % (query, str(args)))
            
        return result[0]
        
    def execute(self, query, *args):
        self.query(query, *args)
        get_db().commit()
        
    def insert(self, query, *args):
        db = get_db()
        cursor = db.cursor()
        cursor.execute(query, args)
        db.commit()
        return cursor.lastrowid
        
    #Artist
    
    Artist = namedtuple("Artist", ["id", "name", "slug", "incomplete", "releases"])
        
    def _make_artist(self, row):
        #Always need to know the releases, might as well get them eagerly
        return self.Artist(*row, releases=self.get_releases_by_artist(row["id"]))
        
    def get_artist(self, artist):
        """Retrieve artist info by id or by slug"""
        
        query = "select * from artists where slug=?" if isinstance(artist, str) \
                else "select * from artists where id=?"
        return self._make_artist(self.query_unique(query, artist))
        
    def get_release_artists(self, release_id):
        """Get all the artists who authored a release"""
        
        return [
            self._make_artist(row) for row in
            self.query("select id, name, slug, incomplete from"
                       " (select artist_id from authorships where release_id=?)"
                       " join artists on artist_id = artists.id", release_id)
        ]
        
    #Release
    
    Release = namedtuple("Release", ["id", "title", "slug", "date", "release_type", "full_art_url", "thumb_art_url", "get_tracks", "get_artists", "get_colors", "get_rating_stats"])
    
    #Handle selection/renaming for joins
    _release_columns = "release_id, title, slug, date, type, full_art_url, thumb_art_url"
    _release_columns_rename = "releases.id as release_id, title, slug, date, type, full_art_url, thumb_art_url"
    #todo rename the actual columns

    def _make_release(self, row):
        release_id = row["release_id"]
        
        return self.Release(*row,
            get_artists=lambda: self.get_release_artists(release_id),
            get_colors=lambda: self.get_release_colors(release_id),
            get_tracks=lambda: self.get_release_tracks(release_id),
            get_rating_stats=lambda: self.get_release_rating_stats(release_id)
        )
        
    def get_releases_by_artist(self, artist_id):
        return [
            self._make_release(row) for row in
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
        return self._make_release(
            #Select the artist and release rows with the right slugs
            # (first, to make the join small)
            #Join them using authorships
            self.query_unique("select " + self._release_columns + " from"
                              " (select artists.id as artist_id from artists where artists.slug=?)"
                              " inner join authorships using (artist_id)"
                              " inner join (select " + self._release_columns_rename + 
                              "             from releases where releases.slug=?)"
                              " using (release_id)", artist_slug, release_slug)
        )
        
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
