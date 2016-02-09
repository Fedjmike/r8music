from functools import partial as p
import sqlite3


# TODO: Properly encapsulate the db.


DB_NAME = 'sample.db'


def lmap(*args, **kwargs):
    return list(map(*args, **kwargs))


def db_results(*args, **kwargs):
    with sqlite3.connect(DB_NAME) as conn:
        return list(conn.cursor().execute(*args, **kwargs))

class ArtistNotFound(Exception):
    pass
    
class ReleaseNotFound(Exception):
    pass

class Artist(object):
    def __init__(self, _id):
        ((self._id, self.name, self.slug),) = db_results(
                'select * from artists where id=?', (_id,))
        self.releases = lmap(p(Release, self), [i for (i,) in db_results(
                'select id from releases where artist_id=?', (self._id,))])

    @classmethod
    def from_slug(cls, slug):
        try:
            ((_id,),) = db_results(
                    'select id from artists where slug=?', (slug,))
            return cls(_id)
        
        except ValueError:
            raise ArtistNotFound()


class Release(object):
    def __init__(self, artist, _id):
        self.artist = artist
        ((self._id,
          self._artist_id,
          self.title,
          self.slug,
          self.date,
          self.reltype,
          self.album_art_url),) = \
                db_results('select * from releases where id=?', (_id,))
        self.tracks = lmap(p(Track, self), [t for (t,) in db_results(
                'select id from tracks where release_id=?', (self._id,))])
        (self.colors, ) = db_results('select color1, color2, color3 from release_colors where release_id=?', (_id,))

    @classmethod
    def from_slug(cls, artist, release_slug):
        try:
            ((_id,),) = db_results(
                    'select id from releases where slug=?', (release_slug,))
            return cls(artist, _id)
            
        except ValueError:
            raise ReleaseNotFound()

    @classmethod
    def from_slugs(cls, artist_slug, release_slug):
        return cls.from_slug(Artist.from_slug(artist_slug), release_slug)


class Track(object):
    def __init__(self, release, _id):
        self.release = release
        ((self._id,
          self._release_id,
          self.title,
          self.slug,
          self.position,
          self.runtime),) = \
                  db_results('select * from tracks where id=?', (_id,))
        self.runtime_string = str(self.runtime//60000) + ":" + str(int(self.runtime/1000) % 60).zfill(2)

    def __repr__(self):
        return self.title
