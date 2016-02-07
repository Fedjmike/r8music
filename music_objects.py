from functools import partial as p
import sqlite3
from lxml import etree
from lxml.builder import E


# TODO: Properly encapsulate the db.


DB_NAME = 'sample.db'


def db_results(*args, **kwargs):
    with sqlite3.connect(DB_NAME) as conn:
        return list(conn.cursor().execute(*args, **kwargs))


class Artist(object):
    def __init__(self, slug, fstyr):
        self.slug, self.fstyr = slug, fstyr
        ((self._id, self.name),) = db_results(
                'select id,name from artists where slug=?', (self.slug,))
        self.releases = map(p(Release, self), self._release_names())

    def _release_names(self):
        return [t for (t,) in db_results(
                'select title from releases where artist_id=?', (self._id,))]

    def _dom(self):
        return E.div(
                 E.h3(self.name),
                 E.ol(*[E.li(r.name) for r in self.releases]),
               )

    def __repr__(self):
        return etree.tostring(self._dom(), pretty_print=True).decode('utf-8')


class Release(object):
    def __init__(self, artist, name):
        self.artist, self.name = artist, name
        ((self._id,),) = db_results(
                'select id from releases where title=? and artist_id=?',
                (self.name, self.artist._id))
        self.tracks = map(p(Track, self), self._track_names())

    def _track_names(self):
        return [t for (t,) in db_results(
                'select title from tracks where release_id=?', (self._id,))]

    def _dom(self):
        return E.div(
                 E.h4(self.name),
                 E.ol(*[E.li(r.name) for r in self.tracks]),
               )

    def __repr__(self):
        return etree.tostring(self._dom()).decode('utf-8')


class Track(object):
    def __init__(self, release, name):
        self.name = name
        self.release = release
        ((self._id,),) = db_results(
                'select id from tracks where title=? and release_id=?',
                (self.name, self.release._id))
        ((self.duration,),) = db_results(
                'select runtime from tracks where id=?', (self._id,))

    def __repr__(self):
        return self.name
