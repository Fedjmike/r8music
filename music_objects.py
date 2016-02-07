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
    def __init__(self, _id):
        ((self._id, self.name, self.slug),) = db_results(
                'select * from artists where id=?', (_id,))
        # map is lazy so the following call invokes a single db lookup.
        self.releases = map(p(Release, self), [i for (i,) in db_results(
                'select id from releases where artist_id=?', (self._id,))])

    @classmethod
    def from_slug(cls, slug):
        ((_id,),) = db_results(
                'select id from artists where slug=?', (slug,))
        return cls(_id)

    def _dom(self):
        return E.div(
                 E.h3(self.name),
                 E.ol(*[E.li(r.title) for r in self.releases]),
               )

    def __repr__(self):
        return etree.tostring(self._dom(), pretty_print=True).decode('utf-8')


class Release(object):
    def __init__(self, artist, _id):
        self.artist = artist
        ((self._id, self.title, self.date, self._artist_id, self.reltype),) = \
                db_results('select * from releases where id=?', (_id,))
        self.tracks = map(p(Track, self), [t for (t,) in db_results(
                'select id from tracks where release_id=?', (self._id,))])

    @classmethod
    def from_slug(cls, artist, slug):
        ((_id,),) = db_results(
                'select id from releases where slug=?', (slug,))
        return cls(artist, _id)

    def _dom(self):
        return E.div(
                 E.h4(self.title),
                 E.ol(*[E.li(r.title) for r in self.tracks]),
               )

    def __repr__(self):
        return etree.tostring(self._dom()).decode('utf-8')


class Track(object):
    def __init__(self, release, _id):
        self.release = release
        ((self._id, self.title, self.runtime, self._release_id),) = db_results(
                'select * from tracks where id=?', (self._id))

    def __repr__(self):
        return self.title
