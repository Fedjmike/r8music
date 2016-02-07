from functools import partial as p
import sqlite3
from lxml import etree
from lxml.builder import E


# TODO: Properly encapsulate the db.


DB_NAME = 'sample.db'


def lmap(*args, **kwargs):
    return list(map(*args, **kwargs))


def db_results(*args, **kwargs):
    with sqlite3.connect(DB_NAME) as conn:
        return list(conn.cursor().execute(*args, **kwargs))


class Artist(object):
    def __init__(self, _id):
        ((self._id, self.name, self.slug),) = db_results(
                'select * from artists where id=?', (_id,))
        self.releases = lmap(p(Release, self), [i for (i,) in db_results(
                'select id from releases where artist_id=?', (self._id,))])

    @classmethod
    def from_slug(cls, slug):
        ((_id,),) = db_results(
                'select id from artists where slug=?', (slug,))
        return cls(_id)

    def _dom(self):
        return E.div({'class': 'artist-main'},
                 E.h1(self.name),
                 E.ol(
                   *[E.li(E.a(r.title,
                       href='/'+self.slug+'/'+r.slug))
                     for r in self.releases]
                 ),
                 E.p(E.a('permalink', href='/a/'+str(self._id))),
               )

    def __repr__(self):
        return etree.tostring(self._dom(), pretty_print=True).decode('utf-8')


class Release(object):
    def __init__(self, artist, _id):
        self.artist = artist
        ((self._id,
          self.title,
          self.date,
          self._artist_id,
          self.reltype,
          self.album_art_url,
          self.slug),) = \
                db_results('select * from releases where id=?', (_id,))
        self.tracks = lmap(p(Track, self), [t for (t,) in db_results(
                'select id from tracks where release_id=?', (self._id,))])

    @classmethod
    def from_slug(cls, artist, release_slug):
        ((_id,),) = db_results(
                'select id from releases where slug=?', (release_slug,))
        return cls(artist, _id)

    @classmethod
    def from_slugs(cls, artist_slug, release_slug):
        return cls.from_slug(Artist.from_slug(artist_slug), release_slug)

    def _dom(self):
        return E.div({'class': 'release'},
                 E.h1(self.title),
                 E.h2(self.artist.name),
                 E.ol({'class': 'tracks'},
                   *[E.li(t.title) for t in self.tracks]
                 ),
                 E.div(
                   E.p('average rating '+str(9.7)),
                   E.ol({'class': 'rating'},
                     *[E.li(str(i)) for i in range(11)]
                   ),
                 ),
               )

    def __repr__(self):
        return etree.tostring(self._dom(), pretty_print=True).decode('utf-8')


class Track(object):
    def __init__(self, release, _id):
        self.release = release
        ((self._id,
          self.position,
          self.title,
          self.runtime,
          self._release_id,
          self.slug),) = \
                  db_results('select * from tracks where id=?', (_id,))
        self.runtime_string = str(self.runtime//60000) + ":" + str(int(self.runtime/1000) % 60).zfill(2)

    def __repr__(self):
        return self.title
