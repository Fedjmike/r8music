from functools import partial as p
import sqlite3


# TODO: Generate some DOM.
# TODO: Make things lazier where appropriate.
# TODO: Properly encapsulate the db.


DB_NAME = 'sample.db'


def db_results(*args, **kwargs):
    with sqlite3.connect(DB_NAME) as conn:
        return list(conn.cursor().execute(*args, **kwargs))


def lmap(*args, **kwargs):
    # map is lazy, lmap isn't.
    return list(map(*args, **kwargs))


class Artist(object):
    def __init__(self, url, fstyr):
        self.url, self.fstyr = url, fstyr
        ((self._id, self.name),) = db_results(
                'select id,name from artists where url=?', (self.url,))
        self.releases = lmap(p(Release, self), self._release_names())

    def _release_names(self):
        return [t for (t,) in db_results(
                'select title from releases where artist_id=?', (self._id,))]

    def __repr__(self):
        return self.name+str(self.releases)


class Release(object):
    def __init__(self, artist, name):
        self.artist, self.name = artist, name
        ((self._id,),) = db_results(
                'select id from releases where title=? and artist_id=?',
                (self.name, self.artist._id))
        self.tracks = lmap(p(Track, self), self._track_names())

    def _track_names(self):
        return [t for (t,) in db_results(
                'select title from tracks where release_id=?', (self._id,))]

    def __repr__(self):
        return self.name


class Track(object):
    def __init__(self, release, name):
        self.name = name
        ((self._id,),) = db_results(
                'select id from tracks where title=? and release_id=?',
                (self.name, self.release._id))
        ((self.duration,),) = db_results(
                'select runtime from tracks where id=?', (self._id,))

    def __repr__(self):
        return self.name
