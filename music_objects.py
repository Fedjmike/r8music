from itertools import product  # Outer product.
from functools import partial as p
from collections import namedtuple
from db import query_db, get_db
from werkzeug import check_password_hash, generate_password_hash
from datetime import datetime

# TODO: Make __init__s lazier.
# TODO: Modify query_db so "[i for (i,) in." is unnecessary.


class lzmap(object):
    # This is an object masquerading as a function.
    def __init__(self, fn, list_):
        self._fn = fn
        self._list = list_  # Must be integer-indexable. (Can be lzmap.)
        self._cache = dict()  # Dict because no such thing as nullable list.

    def __getitem__(self, n):
        try:
            return self._cache[n]
        except KeyError:
            self._cache[n] = self._fn(self._list[n])
            return self.__getitem__(n)

    def __len__(self):
        return len(self._list)


class NotFound(Exception):
    pass
    
class ArtistNotFound(NotFound):
    pass
    
class ReleaseNotFound(NotFound):
    pass

class ReviewNotFound(NotFound):
    pass

class UserNotFound(NotFound):
    pass
    
class UserAlreadyExists(NotFound):
    pass


class Artist(object):
    def __init__(self, _id):
        ((self._id, self.name, self.slug, self.incomplete),) = query_db(
                'select * from artists where id=?', (_id,))
        self.releases = lzmap(Release, [i for (i,) in query_db(
                'select release_id from authorships where artist_id=?', (_id,))])

    @classmethod
    def from_slug(cls, slug):
        try:
            ((_id,),) = query_db(
                    'select id from artists where slug=?', (slug,))
            return cls(_id)
        
        except ValueError:
            raise ArtistNotFound()


def _authorship_exists(authorship):
    (artist_id, release_id) = authorship
    try:
        query_db(
                'select * from authorships where artist_id=? and release_id=?',
                (artist_id, release_id)
            )
        return True
    except ValueError:
        return False


RatingStats = namedtuple('RatingStats', ['mean', 'freq'])


class Release(object):
    def __init__(self, _id):
        ((self._id,
          self.title,
          self.slug,
          self.date,
          self.reltype,
          self.full_art_url,
          self.thumb_art_url),) = \
                query_db('select * from releases where id=?', (_id,))

        self.artists = lzmap(Artist, [a for (a,) in query_db(
                'select artist_id from authorships where release_id=?', (_id,))])
        self.tracks = lzmap(p(Track, self), [t for (t,) in query_db(
                'select id from tracks where release_id=?', (self._id,))])
        self.ratings = lzmap(
                p(Rating, self._id), [u for (u,) in query_db(
                'select user_id from ratings where release_id=?', (self._id,))])
        # "lzmap(User, ..." is just a lazy list of Users, so self.ratings is
        # "[a] Rating [of my]self [for each] User [who reviewed me]".
        # This will read better once the "[u for (u,) in" has gone.
        
        (self.colors, ) = query_db('select color1, color2, color3 from release_colors where release_id=?', (_id,))

        # try:
        #     ((rating_sum, self.rating_frequency),) = \
        #             query_db('select sum, frequency from rating_totals where release_id=?', (self._id,))
        #     self.average_rating = rating_sum / self.rating_frequency
        # except (ValueError, ZeroDivisionError):
        #     self.average_rating = None

    def get_rating_stats(self):
        # This method is directly applicable to Users, also.
        ratings = [r.rating for r in self.ratings if r.rating is not None]
        sum_ratings, n_ratings = sum(ratings), len(ratings)
        try:
            mean_rating = sum_ratings/n_ratings
            return RatingStats(mean=mean_rating, freq=n_ratings)
        except ZeroDivisionError:
            return RatingStats(mean=None, freq=0)

    @classmethod
    def from_slugs(cls, artist_slug, release_slug):
        potential_artists = [a for (a,) in query_db(
                'select id from artists where slug=?', (artist_slug,))]
        potential_releases = [r for (r,) in query_db(
                'select id from releases where slug=?', (release_slug,))]

        ((_, release_id),) = filter(  # Throw an error on clash (for now).
                _authorship_exists,
                product(potential_artists, potential_releases)
            )

        return cls(release_id)


class Track(object):
    def __init__(self, release, _id):
        self.release = release
        ((self._id,
          self._release_id,
          self.title,
          self.slug,
          self.position,
          self.runtime),) = \
                  query_db('select * from tracks where id=?', (_id,))
        if self.runtime:
            self.runtime_string = str(self.runtime//60000) + ":" + str(int(self.runtime/1000) % 60).zfill(2)

    def __repr__(self):
        return self.title


class Rating(object):
    def __init__(self, release_id, user_id):
        try:
            self.release = Release(release_id)
            self.user = User(user_id)
            ((self.rating,),) = query_db(
                    'select rating from ratings '
                    'where release_id=? and user_id=?',
                    (self.release._id, self.user._id))
        except ValueError:
            raise ReviewNotFound()

    @staticmethod
    def set_rating(release_id, user_id, rating):
        db = get_db()
        db.execute(
                'replace into ratings (release_id, user_id, rating) '
                'values (?, ?, ?)',
                (release_id, user_id, rating))
        db.commit()

    @staticmethod
    def unset_rating(release_id, user_id):
        db = get_db()
        # TODO: Error if no rating present?
        db.execute(
                'delete from ratings where release_id=? and user_id=?',
                (release_id, user_id))
        db.commit()


class User(object):
    def __init__(self, _id):
        try:
            ((self._id,
              self.name,
              self.creation),) = \
                      query_db('select id, name, creation from users where id=?', (_id,))
        except ValueError:
            raise UserNotFound()
            
        # TODO: Use Ratings.
        self.ratings = dict(query_db('select release_id, rating from ratings where ratings.user_id=?', (_id,)))

    @staticmethod
    def id_from_name(name):
        try:
            ((_id,),) = query_db('select id from users where name=?', (name,))
            return _id
        except ValueError:
            raise UserNotFound()

    @classmethod
    def from_name(cls, name):
        return cls(cls.id_from_name(name))

    @classmethod
    def register(cls, name, password, email=None, fullname=None):
        """Try to add a new user to the database.
           Perhaps counterintuitively, for security hashing the password is
           delayed until this function. Better that you accidentally hash
           twice than hash zero times and store the password as plaintext."""
    
        if query_db('select id from users where name=?', (name,)):
            raise UserAlreadyExists()
            
        db = get_db()
        cursor = db.cursor()
        cursor.execute('insert into users (name, pw_hash, email, fullname, creation) values (?, ?, ?, ?, ?)',
                       (name, generate_password_hash(password), email, fullname, datetime.now().isoformat()))
        db.commit()
                       
        return cls(cursor.lastrowid)
    
    @staticmethod
    def pw_hash_matches(given_password, _id):
        """For security, the hash is never stored anywhere except the databse.
           For added security, it doesn't even leave this function."""
        ((db_hash,),) = query_db('select pw_hash from users where id=?', (_id,))
        return check_password_hash(db_hash, given_password)
