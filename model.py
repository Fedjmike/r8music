#!/usr/bin/env python3

import sqlite3, arrow
from itertools import count, groupby
from functools import lru_cache
from datetime import datetime
from collections import namedtuple, defaultdict
from enum import Enum
from werkzeug import check_password_hash, generate_password_hash
from flask import url_for

from tools import flatten, chop_suffix, slugify, get_wikipedia_urls
from chromatography import get_palette

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

class GeneralModel:
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

def generate_slug(name, model, table):
    query = "select count(*) from {} where slug=?".format(table)
    is_free = lambda slug: model.query_unique(query, slug)[0] == 0
    
    slug = slugify(name)
    candidates = (slug + ("-%d" % n if n else "") for n in count(0))
    return next(filter(is_free, candidates))
    
class ObjectType(Enum):
    artist = 1
    release = 2
    track = 3

class ActionType(Enum):
    rate = 1
    unrate = 2
    listen = 3
    unlisten = 4
    list = 5
    unlist = 6
    share = 7
    unshare = 8
    
    @property
    def simple_past(self):
        return ["rated", "unrated", "listened to", "unlistened", "list", "unlist", "share", "unshare"][self.value-1]

class ModelObject:
    def init_from_row(self, row, columns):
        for column, value in zip(columns, row):
            setattr(self, column, value)
        
class Artist(ModelObject):
    def __init__(self, model, row):
        self.init_from_row(row, ["id", "name", "slug"])
        
        self.get_releases=lambda: model.get_releases_by_artist(self.id, self.slug)
        self.get_image=lambda: [model.get_link(self.id, link) for link in ["image_thumb", "image"]]
        self.get_description=lambda: model.get_description(self.id)
        self.get_wikipedia_urls=lambda: get_wikipedia_urls(model.get_link(self.id, "wikipedia"))

class Release(ModelObject):
    def __init__(self, model, row, primary_artist_id, primary_artist_slug):
        self.init_from_row(row, ["id", "title", "slug", "date", "release_type", "full_art_url", "thumb_art_url"])
        
        self.get_artists=lambda: model.get_release_artists(self.id, primary_artist_id)
        self.get_palette=lambda: model.get_palette(self.id)
        self.get_tracks=lambda: model.get_release_tracks(self.id)
        self.get_rating_stats=lambda: model.get_rating_stats(self.id)
        
        try:
            self.url = url_for("release_page", release_slug=self.slug, artist_slug=primary_artist_slug)
            
        #Outside Flask app context
        except RuntimeError:
            self.url = None
        
class User(ModelObject):
    def __init__(self, model, row):
        self.init_from_row(row, ["id", "name", "creation"])
        self.creation = arrow.get(self.creation).datetime
        
        self.get_ratings=lambda: model.get_user_ratings(self.id)
        self.get_releases_actioned=lambda: model.get_releases_actioned_by_user(self.id)
        self.get_active_actions=lambda object_id: model.get_active_actions_by_user(self.id, object_id)

class Model(GeneralModel):
    #IDs
    
    def new_id(self, type):
        return self.insert("insert into objects (type) values (?)", type.value)
        
    #Artists
    
    def add_artist(self, name, mbid, incomplete=False):
        #Todo document "incomplete"
        
        slug = generate_slug(name, self, "artists")
        
        artist_id = self.new_id(ObjectType.artist)
        self.insert("insert into artists (id, name, slug, incomplete) values (?, ?, ?, ?)",
                    artist_id, name, slug, mbid if incomplete else None)
        self.set_link(artist_id, "musicbrainz", mbid)
        
        return artist_id
        
    def add_artist_description(self, artist_id, description):
        self.insert("insert into descriptions (id, description) values (?, ?)",
                    artist_id, description)
        
    def get_artist(self, artist):
        """Retrieve artist info by id or by slug"""
        
        query = "select id, name, slug from artists where %s=?" % ("slug" if isinstance(artist, str) else "id")
        return Artist(self, self.query_unique(query, artist))
        
    @lru_cache(maxsize=512)
    def get_release_artists(self, release_id, primary_artist_id=None):
        """Get all the artists who authored a release"""
        
        artists = [
            Artist(self, row) for row in
            self.query("select id, name, slug from"
                       " (select artist_id from authorships where release_id=?)"
                       " join artists on artist_id = artists.id", release_id)
        ]
        
        if primary_artist_id:
            #Put the primary artist first
            ((index, primary_artist),) = [(i, a) for i, a in enumerate(artists) if a.id == primary_artist_id]
            return [primary_artist] + artists[:index] + artists[index+1:]
        
        return artists
        
    #Releases
    
    #Handle selection/renaming for joins
    _release_columns = "release_id, title, slug, date, type, full_art_url, thumb_art_url"
    _release_columns_rename = "releases.id as release_id, title, slug, date, releases.type, full_art_url, thumb_art_url"
    #todo rename the actual columns

    def add_release(self, title, date, type, full_art_url, thumb_art_url, mbid):
        slug = generate_slug(title, self, "releases")
        
        release_id = self.new_id(ObjectType.release)
        self.insert("insert into releases (id, title, slug, date, type, full_art_url, thumb_art_url)"
                    " values (?, ?, ?, ?, ?, ?, ?)", release_id, title, slug, date, type, full_art_url, thumb_art_url)

        self.add_palette_from_image(release_id, thumb_art_url)
        self.set_link(release_id, "musicbrainz", mbid)
                    
        return release_id
        
    def add_author(self, release_id, artist_id):
        self.insert("insert into authorships (release_id, artist_id) values (?, ?)",
                    release_id, artist_id)
    
    def get_releases_by_artist(self, artist_id, artist_slug=None):
        """artist_slug is optional but saves having to look it up"""
        
        if not artist_slug:
            artist_slug = self.query_unique("select slug from artists where id=?", artist_id)
        
        return [
            Release(self, row, artist_id, artist_slug) for row in
            self.query("select " + self._release_columns + " from"
                       " (select release_id from authorships where artist_id=?)"
                       " join releases on releases.id = release_id", artist_id)
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

        return Release(self, row, artist_id, artist_slug)
        
    #Tracks
    
    Track = namedtuple("Track", ["id", "title", "side", "runtime"])
    
    def add_track(self, release_id, title, position, side, runtime):
        slug = generate_slug(title, self, "tracks")
        
        track_id = self.new_id(ObjectType.track)
        self.insert("insert into tracks (id, release_id, title, slug, position, side, runtime) values (?, ?, ?, ?, ?, ?, ?)",
                    track_id, release_id, title, slug, position, side, runtime)

    def get_release_tracks(self, release_id):
        total_runtime = None
        
        def runtime(milliseconds):
            if milliseconds:
                nonlocal total_runtime
                total_runtime = milliseconds + (total_runtime or 0)
                return "%d:%02d" % (milliseconds//60000, (milliseconds/1000) % 60)

        tracks = [
            self.Track(*row, runtime=runtime(milliseconds)) for milliseconds, *row in
            self.query("select runtime, id, title, side from tracks"
                       " where release_id=? order by side asc, position asc", release_id)
        ]
        
        track_no = len(tracks)
        sides = groupby(tracks, lambda track: track.side)
        return [list(tracks) for side_no, tracks in sides], runtime(total_runtime), track_no


    #Object attachments
    
    def add_palette_from_image(self, id, image_url=None):
        palette = get_palette(image_url) if image_url else [None, None, None]
        self.insert("replace into palettes (id, color1, color2, color3)"
                    " values (?, ?, ?, ?)", id, *palette)
        
    def get_palette(self, id):
        return self.query_unique("select color1, color2, color3 from palettes where id=?", id)
        
    def get_description(self, id):
        try:
            return self.query_unique("select description from descriptions where id = (?)", id)[0]
            
        except NotFound:
            return ""

    @lru_cache(maxsize=128)
    def get_link_type_id(self, link_type):
        try:
            return self.query_unique("select id from link_types where type=?", link_type)[0]
            
        except NotFound:
            return self.insert("insert into link_types (type) values (?)", link_type)
        
    def set_link(self, id, link_type, target):
        self.insert("insert or replace into links (id, type_id, target)"
                    " values (?, ?, ?)", id, self.get_link_type_id(link_type), target)

    def get_link(self, id, link_type):
        """link_type can either be the string that identifies a link, or its id"""
        
        try:
            link_type_id = self.get_link_type_id(link_type) if isinstance(link_type, str) else link_type
            
            return self.query_unique("select target from links"
                                 " where id=? and type_id=?", id, link_type_id)[0]
        
        except NotFound:
            return None
        
    #Actions
    
    Action = namedtuple("Action", ["id", "user_id", "object_id", "type", "creation"])
    RatingStats = namedtuple("RatingStats", ["average", "frequency"])
        
    def add_action(self, user_id, object_id, type):
        return self.insert("insert into actions (user_id, object_id, type, creation)"
                           " values (?, ?, ?, ?)", user_id, object_id, type.value, now_isoformat())
        
    def _make_action(self, user_id, action_id, object_id, type_id, creation):
        return self.Action(action_id, user_id, object_id, ActionType(type_id), arrow.get(creation).datetime)
    
    def set_rating(self, user_id, object_id, rating):
        action_id = self.add_action(user_id, object_id, ActionType.rate)
        self.execute("insert into ratings (action_id, rating)"
                     " values (?, ?)", action_id, rating)

    def unset_rating(self, user_id, object_id):
        # TODO: Error if no rating present?
        action_id = self.add_action(user_id, object_id, ActionType.unrate)
        
    def move_actions(self, dest_id, src_id):
        """Moves all actions from one object to another"""
        self.execute("update actions set object_id=? where object_id=?", dest_id, src_id)
        
    def get_active_actions_by_user(self, user_id, object_id):
        latest_by_type = defaultdict(lambda: "0") #A date older than all others
        
        #Oldest of each action type, by that user on that object
        latest_by_type.update({
            type: creation for type, creation in
            self.query("select * from"
                       " (select type, creation from actions"
                       "  where user_id=? and object_id=? order by creation asc)"
                       " group by type", user_id, object_id)
        })
        
        #Pairs of actions and those that undo them
        actions = ["list", "listen", "share"]
        action_pairs = [(name, ActionType[name].value, ActionType["un" + name].value)
                        for name in actions]
        
        #Actions done more recently than undone
        return [name for name, action, antiaction in action_pairs
                if latest_by_type[action] > latest_by_type[antiaction]]
        
    def get_rating_stats(self, object_id):
        ratings = [
            rating for type, rating in
            self.query("select type, rating from"
                       " (select id, user_id, type from actions"
                       "  where object_id=? and (type=? or type=?) order by creation asc)"
                       " left join ratings on id = action_id group by user_id",
                       object_id, ActionType.rate.value, ActionType.unrate.value)
            if type == ActionType.rate.value
        ]
        
        try:
            frequency = len(ratings)
            average = sum(ratings) / frequency
            return self.RatingStats(average=average, frequency=frequency)
            
        except ZeroDivisionError:
            return self.RatingStats(average=None, frequency=0)
        
    def get_user_ratings(self, user_id):
        rows = \
            self.query("select object_id, type, rating from"
                       " (select id, object_id, type from actions"
                       "  where user_id=? and (type=? or type=?) order by creation asc)"
                       " left join ratings on id = action_id group by object_id",
                       user_id, ActionType.rate.value, ActionType.unrate.value)
        
        return {
            object_id: rating
            for object_id, type, rating in rows
            if type == ActionType.rate.value
        }
        
    def _make_release(self, row):
        release_id = row[0]
        
        primary_artist_id, primary_artist_slug = \
            self.query_unique("select id, slug from"
                              " (select artist_id from authorships where release_id=?)"
                              " join artists on artist_id = artists.id limit 1", release_id)
        
        return Release(self, row, primary_artist_id, primary_artist_slug)
        
    def get_releases_actioned_by_user(self, user_id):
        action_values = lambda *actions: [ActionType[action].value for action in actions]
    
        rated = [
            (self._make_release(row), rating) for rating, *row in \
            self.query("select rating, " + self._release_columns_rename + " from"
                       " (select action_id, object_id, type as action_type from"
                       "  (select id as action_id, object_id, type from actions"
                       "   where user_id=? and (type=? or type=?) order by creation asc)"
                       "  group by object_id) natural join ratings"
                       " join releases on id = object_id where action_type=?",
                       user_id, *action_values("rate", "unrate", "rate"))
        ]
        
        listened = [
            self._make_release(row) for row in \
            self.query("select " + self._release_columns_rename + " from"
                       " (select action_id, object_id, type as action_type from"
                       "  (select id as action_id, object_id, type from actions"
                       "   where user_id=? and (type=? or type=?) order by creation asc)"
                       "  group by object_id)"
                       " join releases on id = object_id where action_type=?",
                       user_id, *action_values("listen", "unlisten", "listen"))
        ]
        
        rated_ids = [release.id for release, rating in rated]
        listened_unrated = filter(lambda release: release.id not in rated_ids, listened)
        
        return rated, listened_unrated
        
    #Users
    
    def get_user(self, user):
        """Get user by id or by slug"""
        
        query =   "select id, name, creation from users where %s=?" \
                % ("name" if isinstance(user, str) else "id")
        return User(self, self.query_unique(query, user))
        
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
                       
        return User(self, [user_id, name, creation])
    
    def set_user_pw(self, user, password):
        """user can be a slug or an id"""
        column =  "name" if isinstance(user, str) else "id"
        self.execute("update users set pw_hash=? where %s=?" % column,
                     generate_password_hash(password), user)
    
    def user_pw_hash_matches(self, user, given_password):
        """Confirm the password (hash) of a user, by name or by id.
           For security, the hash is never stored anywhere except the databse.
           For added security, it doesn't even leave this function."""
           
        column =  "name" if isinstance(user, str) else "id"
        db_hash, *row = self.query_unique("select pw_hash, id, name, creation from users"
                                             " where %s=?" % column, user)
        matches = check_password_hash(db_hash, given_password)
        return matches, User(self, row)
        
    #Search
    
    def search(self, query, type):
        if type in ["artists", "users"]:
            #Used to construct SQL strings, must be safe
            table = type
        
        else:
            #error?
            return []
        
        def build_index():
            self.execute("drop table if exists %s_indexed" % table)
            self.execute("create virtual table %s_indexed using fts4 (tokenize=unicode61, id integer, name text)" % table)
            self.execute("insert into %s_indexed (id, name) select id, name from %s" % (table, table))
         
        build_index()
        
        endpoint = chop_suffix(type, "s") + "_page"
        
        columns = {
            "artists": "name, slug",
            "users": "name, name as slug"
        }[type]
        
        return [
            {"type": type, "name": name, "url": url_for(endpoint, slug=slug)}
            for name, slug in
            self.query(("select %s from" % columns) +
                       " (select id as indexed_id from %s_indexed where name match (?) limit 20)"
                       " join %s on %s.id = indexed_id" % (table, table, table), query)
        ]
    
    #Misc
    
    def remove_artist(self, artist):
        """Removes all releases but not the artists collaborated with.
           artist can be a slug or id"""
        
        def remove_attachments(object_id):
            self.execute("delete from palettes where id=?", object_id)
            self.execute("delete from descriptions where id=?", object_id)
            self.execute("delete from links where id=?", object_id)
            
        def remove_actions(object_id):
            self.execute("delete from ratings where action_id in"
                         " (select id from actions where object_id=?)", object_id)
            self.execute("delete from actions where object_id=?", object_id)
            
        def remove_object(object_id, table):
            remove_attachments(object_id)
            remove_actions(object_id)
            self.execute("delete from " + table + " where id=?", object_id)
            self.execute("delete from objects where id=?", object_id)
        
        def remove_tracks(release_id):
            sides, _, _ = self.get_release_tracks(release_id)
            
            for side in sides:
                for track in side:
                    remove_object(track.id, "tracks")
            
        def remove_releases(artist_id):
            for release in self.get_releases_by_artist(artist_id):
                remove_tracks(release.id)
                remove_object(release.id, "releases")
                
        artist = self.get_artist(artist)
        
        remove_releases(artist.id)
        remove_object(artist.id, "artists")
        
    def remove_user(self, user):
        def remove_actions(user_id):
            self.execute("delete from ratings where action_id in"
                         " (select id from actions where user_id=?)", user_id)
            self.execute("delete from actions where user_id=?", user_id)
            
        user = self.get_user(user)
        
        remove_actions(user.id)
        self.execute("delete from users where id=?", user.id)
        
    def merge_artists(self, dest_artist, src_artist):
        """Moves all actions from one artist, their releases and tracks
           to another and theirs. Then removes the source artist.
           Raises an exception if it fails to find a place to move any
           user action."""
        
        class MergeError(Exception): pass
        
        def matches(objects, candidates):
            """Uniquely match every object with a candidate"""
            
            for object in objects:
                try:
                    match = next(c for c in candidates if object.title == c.title)
                    #Don't match this one against any others
                    candidates.remove(match)
                    
                    yield object, match
                
                except StopIteration:
                    raise MergeError("Couldn't match %s, id: %d title: %s" \
                                     % (type(object).__name__, object.id, object.title))
        
        def move_track_actions(dest_release, src_release):
            #get_tracks returns (sides, runtime, track_no)
            src_tracks = flatten(src_release.get_tracks()[0])
            dest_tracks = flatten(dest_release.get_tracks()[0])
            
            for src_track, dest_track in matches(src_tracks, dest_tracks):
                self.move_actions(dest_track.id, src_track.id)
                
        def move_release_actions(dest_artist, src_artist):
            dest_releases = dest_artist.get_releases()
            src_releases = src_artist.get_releases()
            
            for src_release, dest_release in matches(src_releases, dest_releases):
                move_track_actions(dest_release, src_release)
                self.move_actions(dest_release.id, src_release.id)
                
        dest_artist = self.get_artist(dest_artist)
        src_artist = self.get_artist(src_artist)
        
        move_release_actions( dest_artist, src_artist)
        self.move_actions(dest_artist.id, src_artist.id)
            
        self.remove_artist(src_artist.id)
        
if __name__ == "__main__":
    import sys
    from contextlib import closing
    
    with closing(Model()) as model:
        program, command, *sys.argv = sys.argv
        
        if command == "remove":
            try:
                noun, *args = sys.argv
                action =      model.remove_artist if noun == "artist" \
                         else model.remove_user if noun == "user" \
                         else None
                
                for obj in args:
                    try:
                        action(obj)
                        
                    except NotFound:
                        print("%s not found" % obj)
                
                if not action:
                    raise TypeError()
                
                elif len(args) == 0:
                    print("No arguments given to `%s %s`" % (command, noun))
                    
            #Unpacked []
            except ValueError:
                print("No subcommand given to `%s`" % command)
                
            #Called None
            except TypeError:
                print("Invalid subcommand `%s` given to `%s`" % (noun, command))
            
        elif command == "import_artist":
            raise NotImplemented()
            
        elif command == "set_pw":
            model.set_user_pw(args[0], args[1])
            
        else:
            print("Command not selected")