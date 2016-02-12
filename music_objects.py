from itertools import product  # Outer product.
from functools import partial as p
from db import query_db, get_db
from werkzeug import check_password_hash, generate_password_hash

class lzmap(object):
    # This is an object masquerading as a function.
    def __init__(self, fn, listable):
        self._fn = fn
        self._list = listable  # Don't actually turn it into a list yet...
        self._cache = dict()  # Dict because no such thing as nullable list.

    def __getitem__(self, n):
        try:
            return self._cache[n]
        except KeyError:
            self._list = list(self._list)  # Idempotent.
            self._cache[n] = self._fn(self._list[n])
            return self.__getitem__(n)

    def __len__(self):
        self._list = list(self._list)
        return len(self._list)


class NotFound(Exception):
    pass
    
class ArtistNotFound(NotFound):
    pass
    
class ReleaseNotFound(NotFound):
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
                'select release_id from authors where artist_id=?', (_id,))])

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
                'select * from authors where artist_id=? and release_id=?',
                (artist_id, release_id)
            )
        return True
    except ValueError:
        return False


class Release(object):
    def __init__(self, _id):
        ((self._id,
          self.title,
          self.slug,
          self.date,
          self.reltype,
          self.album_art_url),) = \
                query_db('select * from releases where id=?', (_id,))

        self.artists = lzmap(Artist, [a for (a,) in query_db(
                'select artist_id from authors where release_id=?', (_id,))])
        self.tracks = lzmap(p(Track, self), [t for (t,) in query_db(
                'select id from tracks where release_id=?', (self._id,))])
        
        try:
            ((rating_sum, self.rating_frequency),) = \
                    query_db('select sum, frequency from rating_totals where release_id=?', (self._id,))
            self.average_rating = rating_sum / self.rating_frequency
        except (ValueError, ZeroDivisionError):
            self.average_rating = None

        (self.colors, ) = query_db('select color1, color2, color3 from release_colors where release_id=?', (_id,))

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
        else:
            self.runtime_string = "??:??"

    def __repr__(self):
        return self.title


class User(object):
    def __init__(self, _id):
        try:
            ((self._id,
              self.name),) = \
                      query_db('select id, name from users where id=?', (_id,))
        except ValueError:
            raise UserNotFound()
            
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
    def register(cls, name, password):
        """Try to add a new user to the database.
           Perhaps counterintuitively, for security hashing the password is
           delayed until this function. Better that you accidentally hash
           twice than hash zero times and store the password as plaintext."""
    
        if query_db('select id from users where name=?', (name,)):
            raise UserAlreadyExists()
            
        db = get_db()
        cursor = db.cursor()
        cursor.execute('insert into users (name, pw_hash) values (?, ?)',
                       (name, generate_password_hash(password)))
        db.commit()
                       
        return cls(cursor.lastrowid)
    
    @staticmethod
    def pw_hash_matches(given_password, _id):
        """For security, the hash is never stored anywhere except the databse.
           For added security, it doesn't even leave this function."""
        ((db_hash,),) = query_db('select pw_hash from users where id=?', (_id,))
        return check_password_hash(db_hash, given_password)
