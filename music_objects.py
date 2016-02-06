from functools import partial as p


def lmap(*args, **kwargs):
    # map is lazy, lmap isn't.
    return list(map(*args, **kwargs))


class Artist(object):
    def __init__(self, name, fstyr):
        self.name, self.fstyr = name, fstyr
        self.releases = lmap(p(Release, self), self._db_query())

    def _db_query(self):
        # We'll do an SQL query (or whatever) here based on fields of self
        # and return a list of things each passable to the Release constructor.
        return lmap(lambda n: self.name+':release'+str(n), range(3))

    def __repr__(self):
        return self.name


class Release(object):
    def __init__(self, artist, name):
        self.artist, self.name = artist, name
        self.tracks = lmap(p(Track, self), self._db_query())

    def _db_query(self):
        return lmap(lambda n: self.name+':track'+str(n), range(10))

    def __repr__(self):
        return self.name


class Track(object):
    def __init__(self, release, name):
        self.name = name
        self.duration = self._db_query()

    def _db_query(self):
        return 180

    def __repr__(self):
        return self.name
