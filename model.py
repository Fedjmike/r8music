#!/usr/bin/env python3

import sqlite3, arrow
from itertools import count, groupby
from functools import lru_cache
from operator import itemgetter
from collections import namedtuple, defaultdict
from enum import Enum
from werkzeug import check_password_hash, generate_password_hash
from flask import url_for

from tools import flatten, uniq, chop_suffix, slugify, get_wikipedia_urls, execution_time, profiled, avatar_url
from template_tools import url_for_release
from chromatography import get_palette

class NotFound(Exception):
    pass
    
class AlreadyExists(Exception):
    pass
    
def connect_db():
    return sqlite3.connect("sample.db")

class GeneralModel:
    def __init__(self, connect_db=connect_db):
        self.db = connect_db()
        self.db.row_factory = sqlite3.Row
        
    def close(self):
        self.db.close()
        
    def __enter__(self):
        return self
        
    def __exit__(self, type, value, traceback):
        self.close()

    def query(self, query, *args):
        return self.db.execute(query, args).fetchall()
        
    def query_unique(self, query, *args, fallback=None):
        result = self.query(query, *args)
        
        if len(result) == 0:
            if fallback:
                return fallback
            
            else:
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
    pick = 9
    unpick = 10
    
    @property
    def simple_past(self):
        return ["rated", "unrated", "listened to", "unlistened", "listed", "unlisted", "shared", "unshared"][self.value-1]

class UserType(Enum):
    user = 1
    admin = 2

class RatingStats:
    def __init__(self, ratings):
        try:
            self.frequency = len(ratings)
            self.average = sum(ratings) / self.frequency
            
        except ZeroDivisionError:
            self.average = None

class ModelObject:
    def init_from_row(self, row, columns):
        for column, value in zip(columns, row):
            setattr(self, column, value)
    
    def __eq__(self, other):
        return self.id == other.id
        
class Artist(ModelObject):
    def __init__(self, model, row):
        self.init_from_row(row, ["id", "name", "slug"])
        
        self.get_releases = lambda: model.get_releases_by_artist(self)
        self.get_image = lambda: [model.get_link(self.id, link) for link in ["image_thumb", "image"]]
        self.get_description = lambda: model.get_description(self.id)
        self.get_wikipedia_urls = lambda: get_wikipedia_urls(model.get_link(self.id, "wikipedia"))
        self.get_external_links = lambda: model.get_external_links(self.id, "artist")

class Release(ModelObject):
    def __init__(self, model, row, primary_artist_id, primary_artist_slug):
        self.init_from_row(row, ["id", "title", "slug", "date", "release_type", "full_art_url", "thumb_art_url"])
        self.url = url_for_release(primary_artist_slug, self.slug)
        
        def get_artists():
            artists = model.get_release_artists(self.id)
            
            #Put the primary artist first
            index, primary_artist = next((i, a) for i, a in enumerate(artists) if a.id == primary_artist_id)
            return [primary_artist] + artists[:index] + artists[index+1:]
            
        def get_tracks():
            tracks = model.get_release_tracks(self.id)
            track_no = len(tracks)
            total_runtime = sum(track.runtime for track in tracks if track.runtime)
            
            def runtime_str(milliseconds):
                if milliseconds:
                    return "%d:%02d" % (milliseconds//60000, (milliseconds/1000) % 60)

            tracks = [track._replace(runtime=runtime_str(track.runtime)) for track in tracks]
            sides = groupby(tracks, lambda track: track.side)
            return [list(tracks) for side_no, tracks in sides], runtime_str(total_runtime), track_no
            
        def get_next_releaseses():
            for artist in get_artists():
                #If this release is an album, only consider albums
                predicate =      (lambda r: True) if self.release_type != "Album" \
                            else (lambda release: release.release_type == "Album")
                other_releases = sorted(filter(predicate, artist.get_releases()),
                                        key=lambda release: release.date)
                
                #The index of this release
                index = next(i for i, r in enumerate(other_releases) if r.id == self.id)
                
                previous = other_releases[index-1] if index != 0 else None
                _next = other_releases[index+1] if index != len(other_releases)-1 else None
                yield artist, previous, _next

        self.get_artists = get_artists
        self.get_tracks = get_tracks
        self.get_next_releaseses = get_next_releaseses
        self.get_palette = lambda: model.get_palette(self.id)
        self.get_external_links = lambda: model.get_external_links(self.id, "release")
        
        self.get_rating_stats = lambda: RatingStats(model.get_ratings(self.id))
        self.get_reviews = lambda: model.get_reviews(self.id)
        self.get_review_no = lambda: model.get_review_no(self.id)
        
class User(ModelObject):
    def __init__(self, model, row):
        self.init_from_row(row, ["id", "name", "email", "type", "creation"])
        self.type = UserType(self.type)
        self.creation = arrow.get(self.creation)
        self.timezone = model.get_user_timezone(self.id)
        self.avatar_url = avatar_url(self.email if self.email else self.name)
        
        def get_releases_listened_unrated():
            listened = model.get_releases_actioned_by_user(self.id, "listen")
            rated_ids = [release.id for release, rating in model.get_releases_rated_by_user(self.id)]
            return filter(lambda release: release.id not in rated_ids, listened)
            
        def get_releases_listed():
            return model.get_releases_actioned_by_user(self.id, "list")
        
        self.get_ratings = lambda: model.get_ratings_by_user(self.id)
        self.get_releases_rated = lambda: model.get_releases_rated_by_user(self.id)
        self.get_releases_listened = lambda: model.get_releases_actioned_by_user(self.id, "listen")
        self.get_releases_listened_unrated = get_releases_listened_unrated
        self.get_releases_listed = get_releases_listed
        
        self.get_picks = lambda release_id: model.get_picks(self.id, release_id)
        self.get_pick_no = lambda: model.get_user_pick_no(self.id)
        
        self.get_active_actions = lambda object_id: model.get_active_actions(self.id, object_id)
        self.get_rating_descriptions = lambda: model.get_user_rating_descriptions(self.id)
        
        self.get_followers = lambda: model.get_followers(self.id)
        self.get_follow = lambda user_id: model.get_following_since(self.id, user_id)
        
        self.get_activity_feed = lambda offset=0: model.get_activity_feed(self.id, offset=offset)
        self.get_activity = lambda: model.get_activity_by_user(self.id)
        
class Action(ModelObject):
    def __init__(self, id, type, creation, object_id, object_title, object_slug, object_thumb,
                 user, artists):
        self.id = id
        self.type = ActionType(type)
        self.creation = arrow.get(creation)
        self.user = user
        self.object = dict(id=object_id, title=object_title, thumb_art_url=object_thumb, artists=artists,
                           url=url_for_release(artists[0]["slug"], object_slug))

class Model(GeneralModel):
    #IDs
    
    def new_id(self, type):
        return self.insert("insert into objects (type) values (?)", type.value)
        
    #Artists
    
    def add_artist(self, name, mbid):
        slug = generate_slug(name, self, "artists")
        
        artist_id = self.new_id(ObjectType.artist)
        self.insert("insert into artists (id, name, slug) values (?, ?, ?)",
                    artist_id, name, slug)
        self.set_link(artist_id, "musicbrainz", mbid)
        
        return artist_id
        
    def get_artist(self, artist):
        """Retrieve artist info by id or by slug"""
        
        query = "select id, name, slug from artists where %s=?" % ("slug" if isinstance(artist, str) else "id")
        return Artist(self, self.query_unique(query, artist))
        
    @lru_cache(maxsize=512)
    def get_release_artists(self, release_id):
        """Get all the artists who authored a release"""
        
        return [
            Artist(self, row) for row in
            self.query("select id, name, slug from"
                       " (select artist_id from authorships where release_id=?)"
                       " join artists on artist_id = artists.id", release_id)
        ]
        
    #Releases
    
    #Handle selection/renaming for joins
    _release_columns = "release_id, title, slug, date, type, full_art_url, thumb_art_url"
    _release_columns_rename = "releases.id as release_id, title, slug, date, releases.type, full_art_url, thumb_art_url"
    
    def add_release(self, title, date, type, full_art_url, thumb_art_url, mbid):
        slug = generate_slug(title, self, "releases")
        
        release_id = self.new_id(ObjectType.release)
        self.insert("insert into releases (id, title, slug, date, type, full_art_url, thumb_art_url)"
                    " values (?, ?, ?, ?, ?, ?, ?)", release_id, title, slug, date, type, full_art_url, thumb_art_url)

        self.add_palette_from_image(release_id, thumb_art_url)
        self.set_link(release_id, "musicbrainz", mbid)
                    
        return release_id
        
    def add_author(self, release_id, artist_id):
        self.insert("replace into authorships (release_id, artist_id) values (?, ?)",
                    release_id, artist_id)
    
    def get_releases_by_artist(self, artist):
        """artist is the Artist object"""
        
        return [
            Release(self, row, artist.id, artist.slug) for row in
            self.query("select " + self._release_columns + " from"
                       " (select release_id from authorships where artist_id=?)"
                       " join releases on releases.id = release_id", artist.id)
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
        return [
            self.Track(*row) for row in
            self.query("select id, title, side, runtime from tracks"
                       " where release_id=? order by side asc, position asc", release_id)
        ]

    #Object attachments
    
    def add_palette_from_image(self, id, image_url=None):
        self.set_palette(id, get_palette(image_url) if image_url else [None, None, None])
        
    def set_palette(self, id, palette):
        self.insert("replace into palettes (id, color1, color2, color3)"
                    " values (?, ?, ?, ?)", id, *palette)
        
    def get_palette(self, id):
        return self.query_unique("select color1, color2, color3 from palettes"
                                 " where id=?", id, fallback=(None, None, None))
        
    def set_description(self, artist_id, description):
        self.insert("replace into descriptions (id, description)"
                    " values (?, ?)", artist_id, description)
        
    def get_description(self, id):
        return self.query_unique("select description from descriptions"
                                 " where id = (?)", id, fallback=("",))[0]
        
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
        
        link_type_id = self.get_link_type_id(link_type) if isinstance(link_type, str) else link_type
            
        return self.query_unique("select target from links where id=? and type_id=?",
                                 id, link_type_id, fallback=(None,))[0]
        
    def get_external_links(self, id, mb_type):
        sites = [
            "AZLyrics", "Allmusic", "Bandcamp", "Facebook",
            "Twitter", "SoundCloud", "UltimateGuitar",
            #For some sites an ID or title is stored, not an URL
            ("Wikipedia", lambda title: "//en.wikipedia.org/wiki/" + title),
            ("MusicBrainz", lambda mbid: "//musicbrainz.org/%s/%s" % (mb_type, mbid))
        ]
        
        for site in sites:
            site, build_url = site if isinstance(site, tuple) else (site, lambda x: x)
            link = self.get_link(id, site.lower())
            
            if link:
                yield site, build_url(link)
        
    def mbid_in_links(self, mbid):
        return self.query_unique("select exists(select 1 from links"
                                  " where target=? limit 1 )", mbid)[0]


    #Actions
    
    Action = namedtuple("Action", ["id", "user", "object", "type", "creation"])
        
    def add_action(self, user_id, object_id, type):
        #Rating implies having listened (transitively, it also unlists)
        if type == ActionType["rate"]:
            self.add_action(user_id, object_id, ActionType["listen"])
            
        #Listening resets "to listen" status
        if type == ActionType["listen"]:
            self.add_action(user_id, object_id, ActionType["unlist"])
            
        if not type.name.startswith('un'):
            action_id = self.insert("insert into actions (user_id, object_id, type, creation)"
                                    " values (?, ?, ?, ?)",
                                    user_id, object_id, type.value, arrow.utcnow().timestamp)

        try:
            (previous_active_action,) = \
                self.query_unique("select action_id from active_actions_view"
                                  " where user_id=? and object_id=? and type=?", user_id, object_id,
                                  type.value if not type.name.startswith('un') else ActionType[type.name[2:]].value)
            self.execute("delete from active_actions where action_id=?", previous_active_action)

        except NotFound:
            pass

        if not type.name.startswith('un'):
            self.execute("insert into active_actions values (?)", action_id)
            return action_id
        
    def _make_action(self, user, action_id, object, type_id, creation):
        return self.Action(action_id, user, object, ActionType(type_id), arrow.get(creation))
    
    def set_rating(self, user_id, object_id, rating=None):
        action_id = self.add_action(user_id, object_id, ActionType["rate" if rating else "unrate"])
        
        if rating:
            self.execute("insert into ratings (action_id, rating)"
                         " values (?, ?)", action_id, rating)
    
    def move_actions(self, dest_id, src_id):
        """Moves all actions from one object to another"""
        self.execute("update actions set object_id=? where object_id=?", dest_id, src_id)

    def get_picks(self, user_id, release_id):
        return [
            pick for (pick,) in \
            self.query("select id from tracks join active_actions_view on id = object_id"
                       " where user_id=? and release_id=?", user_id, release_id)
        ]
            
    def get_user_pick_no(self, user_id):
        return self.query_unique("select count(*) from active_actions_view"
                                 " where user_id=? and type=?",
                                 user_id, ActionType['pick'].value)[0]

    def _get_activity(self, primary_user_id, limit, offset, friends=False):
        #todo not just releases
        rows = self.query("select a.action_id, a.type, a.creation,"
                          " r.id, r.title, r.slug, r.thumb_art_url, user_id, artists.name, artists.slug from"
                          " active_actions_view a join users u on user_id = u.id"
                          " join releases r on object_id = r.id"
                          " join authorships on object_id = release_id"
                          " join artists on artist_id = artists.id" + \
                          (" where u.id = ?" if not friends else \
                           " where u.id in (select user_id from followerships"
                           " where follower=? union select ? as user_id)") + \
                          " order by a.creation desc limit ? offset ?",
                          *[primary_user_id, primary_user_id, limit, offset] if friends else [primary_user_id, limit, offset])
        
        action_type, user_id, object_id, artist_name, artist_slug = (itemgetter(n) for n in [1, 7, 3, 8, 9])
        
        action_priorities = {"rate": 1, "listen": 2, "list": 3, "share": 4}
        action_priorities = {ActionType[k].value: v for k, v in action_priorities.items()}
        
        yield offset + len(rows)
        
        for _, rows in groupby(rows, key=lambda row: (object_id(row), user_id(row))):
            rows = list(rows) #groupby uses generators
            user = self.get_user(user_id(rows[0]))
            artists = [dict(name=artist_name(row), slug=artist_slug(row))
                       for row in uniq(rows, key=artist_slug)]
            
            highest_priority_action = sorted(rows, key=lambda r: action_priorities[action_type(r)])[0]
            row = list(highest_priority_action)[:7] #Excluding user and artist columns
            
            yield Action(*row, user=user, artists=artists)
        
    def get_activity_by_user(self, user_id, limit=20, offset=0):
        offset, *actions = self._get_activity(user_id, limit, offset)
        return offset, actions
        
    def get_activity_feed(self, user_id, limit=20, offset=0):
        offset, *actions = self._get_activity(user_id, limit, offset, friends=True)
        return offset, actions
        
    def get_active_actions(self, user_id, object_id):
        return [
            ActionType(type).name for (type,) in
            self.query("select type from active_actions_view"
                       " where user_id=? and object_id=?", user_id, object_id)
        ]
        
    def get_ratings(self, object_id):
        return [
            rating for (rating,) in
            self.query("select rating from active_actions_view"
                       " join ratings using (action_id) where object_id=?", object_id)
        ]
    
    def get_ratings_by_user(self, user_id):
        return {
            object_id: rating for object_id, rating in
            self.query("select object_id, rating from active_actions_view"
                       " join ratings using (action_id) where user_id=?", user_id)
        }
        
    def _make_release(self, row):
        release_id = row[0]
        
        primary_artist_id, primary_artist_slug = \
            self.query_unique("select id, slug from"
                              " (select artist_id from authorships where release_id=?)"
                              " join artists on artist_id = artists.id limit 1", release_id)
        
        return Release(self, row, primary_artist_id, primary_artist_slug)
        
    def get_releases_rated_by_user(self, user_id):
        return [
            (self._make_release(row), rating) for rating, *row in
            self.query("select rating, " + self._release_columns_rename +
                       " from active_actions_view a join releases on id = object_id"
                       " join ratings using (action_id)"
                       " where user_id=? and a.type=?", user_id, ActionType.rate.value)
        ]
        
    def get_releases_actioned_by_user(self, user_id, action):
        return [
            self._make_release(row) for row in
            self.query("select " + self._release_columns_rename +
                       " from active_actions_view a join releases on id = object_id"
                       " where user_id=? and a.type=?", user_id, ActionType[action].value)
        ]
        
    #Reviews
    
    def get_reviews(self, object_id):
        return []
        
    def get_review_no(self, object_id):
        return 0
        
    #Users
    
    def get_user(self, user):
        """Get user by id or by slug"""
        
        query =   "select id, name, email, type, creation from users where %s=?" \
                % ("name" if isinstance(user, str) else "id")
        return User(self, self.query_unique(query, user))
        
    def user_exists(self, name):
        return self.query("select id from users where name=?", name)
        
    def register_user(self, name, password, email=None, fullname=None, timezone=None):
        """Try to add a new user to the database.
           Perhaps counterintuitively, for security hashing the password is
           delayed until this function. Better that you accidentally hash
           twice than hash zero times and store the password as plaintext."""
    
        if self.user_exists(name):
            raise AlreadyExists()
            
        creation = arrow.utcnow().timestamp
        user_id = self.insert("insert into users (name, pw_hash, email, fullname, type, creation)"
                              " values (?, ?, ?, ?, ?, ?)", name, generate_password_hash(password),
                              email, fullname, UserType.user.value, creation)
        
        self.set_user_timezone(user_id, timezone)
        
        return User(self, (user_id, name, email, UserType.user, creation))
    
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
        db_hash, *row = self.query_unique("select pw_hash, id, name, email, type, creation from users"
                                          " where %s=?" % column, user)
        matches = check_password_hash(db_hash, given_password)
        return matches, User(self, row)
        
    def set_user_email(self, user_id, email):
        self.execute("update users set email=? where id=?", email, user_id)
        
    def set_user_type(self, user_id, type):
        self.execute("update users set type=? where id=?", UserType[type].value, user_id)
        
    def set_user_timezone(self, user_id, timezone=None):
        self.execute("replace into user_timezones (user_id, timezone)"
                     "values (?, ?)", user_id, timezone if timezone else "Europe/London")
        
    def get_user_timezone(self, user_id):
        return self.query_unique("select timezone from user_timezones"
                                 " where user_id=?", user_id, fallback=("Europe/London",))[0]
        
    def set_user_rating_description(self, user_id, rating, description):
        if description:
            self.execute("replace into user_rating_descriptions (user_id, rating, description)"
                         " values (?, ?, ?)", user_id, rating, description)
        
        else:
            self.execute("delete from user_rating_descriptions"
                         " where user_id=? and rating=?", user_id, rating)
        
    def get_user_rating_descriptions(self, user_id):
        descriptions = {8: "Amazing", 7: "Excellent", 6: "Great", 5: "Very good", 4: "Good", 3: "Alright", 2: "One or two good parts", 1: "Nothing good"}
        descriptions.update({
            rating: description for rating, description in
            self.query("select rating, description from user_rating_descriptions"
                       " where user_id=?", user_id)
        })
        return descriptions
        
    def follow(self, follower_id, user_id):
        creation = arrow.utcnow().timestamp
        self.execute("insert into followerships (follower, user_id, creation)"
                     " values (?, ?, ?)", follower_id, user_id, creation)
                     
    def unfollow(self, follower_id, user_id):
        self.execute("delete from followerships where follower=? and user_id=?",
                     follower_id, user_id)
        
    def get_followers(self, user_id):
        return [
            dict(name=name, since=arrow.get(creation)) for name, creation in
            self.query("select u.name, f.creation from users u join followerships f on u.id = follower"
                       " where user_id=?", user_id)
        ]
        
    def get_following_since(self, follower_id, user_id):
        rows = self.query("select creation from followerships"
                          " where follower=? and user_id=?", follower_id, user_id)
        return arrow.get(rows[0]["creation"]) if rows else None
        
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
            "artists": "id, name, slug",
            "users": "id, name, name as slug"
        }[type]
        
        return [
            {"id": id, "type": type, "name": name, "url": url_for(endpoint, slug=slug)}
            for id, name, slug in
            self.query(("select %s from" % columns) +
                       " (select id as indexed_id from %s_indexed where name match (?) limit 20)"
                       " join %s on %s.id = indexed_id" % (table, table, table), query+'*')
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
        
        def remove_tracks(release):
            sides, _, _ = release.get_tracks()
            
            for side in sides:
                for track in side:
                    remove_object(track.id, "tracks")
            
        def remove_releases(artist):
            for release in artist.get_releases():
                remove_tracks(release)
                remove_object(release.id, "releases")
                
        artist = self.get_artist(artist)
        
        remove_releases(artist)
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
    
    with Model() as model:
        program, command, *args = sys.argv
        
        if command == "remove":
            try:
                noun, *args = args
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
