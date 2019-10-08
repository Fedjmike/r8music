import shelve, musicbrainzngs
from datetime import datetime, timezone
from django.conf import settings
from django.db import transaction

from django.contrib.auth.models import User
from r8music.profiles.models import UserSettings, UserProfile, UserRatingDescription, Followership
from r8music.music.models import Artist, Release, ReleaseType, Track, Tag, DiscogsTag, ArtistExternalLink, ReleaseExternalLink, generate_slug_tracked
from r8music.actions.models import SaveAction, ListenAction, RateAction, PickAction

from r8music.importation.models import ArtistMBLink, ReleaseMBLink, ReleaseDuplication
from r8music.v1transfer.models import UserV1Link, TagV1Link, ArtistV1Link, ReleaseV1Link, TrackV1Link, ActionV1Link

from r8music.v1.model import Model, UserType, ObjectType, ActionType, NotFound

from r8music.v1transfer.auth import werkzeug_pw_hash_to_django

class IDMap:
    """Maps from IDs in the old database to those in the new models."""
    
    def __init__(self, link_model, kind_name):
        """Instantiates the map from the entries of a particular V1Link model.
           kind_name is the name of the field in the link model in which the
           new object is stored."""
        self.kind_name = kind_name
        self.link_model = link_model
        self.update()
        
    def update(self):
        new_id_field = self.kind_name + "_id"
        self.id_map = {
            link["old_id"]: link[new_id_field]
            for link in self.link_model.objects.values(new_id_field, "old_id").all()
        }
        
    def map(self, id):
        try:
            return self.id_map[id]
            
        except IndexError as e:
            raise ValueError("%s id=%d was not found" % (self.kind_name, id)) from e

class Transferer:
    """Transfers data from the V1 database into the new Django models, as well as
       adding link objects which map between the two databases by ID.
       
       In most cases, for speed, one query is used to select all the relevant
       columns and join the necessary tables, for all rows of a table. If not,
       the data is navigated via the objects produced by v1.model.Model - slower,
       but simpler to write.
       
       New objects are created in bulk, except those whose IDs are needed for
       subsequent operations (which bulk_create cannot provide).
       
       Some methods are wrapped in an atomic operation decorator, to avoid writing
       to the filesystem after every insertion.
       
       Objects and IDs from the old model are simply referred to as 'artist' and
       'release_id' etc. Those of the new model are referred to as 'new_artist'
       etc."""

    def __init__(self, model, mbid_shelve_name="mbids"):
        self.model = model
        
        self.mbid_shelve_name = mbid_shelve_name
        
        #These are used to avoid numerous individual queries to the V1Link models,
        #and must updated when new links are added.
        self.new_user_ids = IDMap(UserV1Link, "user")
        self.new_tag_ids = IDMap(TagV1Link, "tag")
        self.new_artist_ids = IDMap(ArtistV1Link, "artist")
        self.new_release_ids = IDMap(ReleaseV1Link, "release")
        self.new_track_ids = IDMap(TrackV1Link, "track")
        
    #
    
    def query_release_group_mbids(self):
        """Query MusicBrainz for release group MBIDs, since the V1 database
           only stored the MBIDs of the release, not its release group."""
           
        musicbrainzngs.set_useragent(*settings.MUSICBRAINZ_USERAGENT)
        
        mb_type_id = self.model.get_link_type_id("musicbrainz")
        
        with shelve.open(self.mbid_shelve_name, writeback=True) as db:
            if "mbids" not in db:
                db["mbids"] = {}
            
            for release_id, release_mbid in self.model.query(
                "select id, target from links where type_id=?",
                mb_type_id
            ):
                if release_id in db["mbids"]:
                    continue
                
                try:
                    release_group_mbid = musicbrainzngs.get_release_by_id(
                        release_mbid, includes=["release-groups"]
                    )["release"]["release-group"]["id"]
                    
                except musicbrainzngs.ResponseError:
                    release_group_mbid = None
                
                db["mbids"][release_id] = (release_mbid, release_group_mbid)
                
            self.release_mbids = db["mbids"]
    
    #
    
    def transfer_user(self, user_id):
        user = self.model.get_user(user_id)
        (password_hash,) = self.model.query_unique("select pw_hash from users where id=?", user.id)
        
        new_user = User.objects.create_user(
            username=user.name,
            email=user.email,
            date_joined=user.creation.datetime
        )
        
        new_user.password = werkzeug_pw_hash_to_django(password_hash)
        new_user.save()
        
        if user.type == UserType.admin:
            new_user.is_superuser = new_user.is_staff = True
            new_user.save()
        
        UserSettings.objects.create(
            user=new_user,
            timezone=user.timezone,
            listen_implies_unsave=user.get_listen_implies_unsave()
        )

        UserProfile.objects.create(
            user=new_user,
            avatar_url=user.avatar_url
        )
        
        for rating, description in user.get_rating_descriptions().items():
            UserRatingDescription.objects.create(user=new_user.profile, rating=rating, description=description)
        
        return UserV1Link(
            user=new_user,
            old_id=user.id
        )
         
    @transaction.atomic
    def transfer_all_users(self):
        UserV1Link.objects.bulk_create([
            self.transfer_user(user_id)
            for (user_id,) in self.model.query("select id from users")
        ])
        
        self.new_user_ids.update()
        
        Followership.objects.bulk_create([
            Followership(
                follower_id=self.new_user_ids.map(follower_id),
                user_id=self.new_user_ids.map(user_id),
                creation=datetime.fromtimestamp(creation, timezone.utc)
            )
            for follower_id, user_id, creation in self.model.query(
                "select follower, user_id, creation from followerships"
            )
        ])
        
    #

    def transfer_tag(self, tag_id, name, title, description, owner_id):
        fields = dict(
            name=name, title=title, description=description,
            owner_id=self.new_user_ids.map(owner_id) if owner_id else None
        )
        
        try:
            (discogs_name,) = self.model.query_unique(
                "select discogs_name from discogs_tags where tag_id=?", tag_id
            )
            new_tag = DiscogsTag.objects.create(discogs_name=discogs_name, **fields)
            
        except IndexError:
            new_tag = Tag.objects.create(**fields)
        
        return TagV1Link(tag=new_tag, old_id=tag_id)
    
    @transaction.atomic
    def transfer_all_tags(self):
        TagV1Link.objects.bulk_create([
            self.transfer_tag(*row)
            for row in self.model.query("select id, name, title, description, owner_id from tags")
        ])
        
        self.new_tag_ids.update()
        
    #
    
    def transfer_artist(self, artist_id, used_slugs):
        artist = self.model.get_artist(artist_id)
        mb_type_id = self.model.get_link_type_id("musicbrainz")
        (mbid,) = self.model.query_unique(
            "select target from links where type_id=? and id=?", mb_type_id, artist_id
        )
        
        new_artist = Artist.objects.create(
            name=artist.name,
            slug=generate_slug_tracked(used_slugs, artist.name),
            description=artist.get_description()
        )
        
        ArtistMBLink.objects.create(artist=new_artist, mbid=mbid)
        
        ArtistExternalLink.objects.bulk_create([
            ArtistExternalLink(artist=new_artist, name=name, url=url)
            for name, url in artist.get_external_links()
        ])
        
        return ArtistV1Link(artist=new_artist, old_id=artist_id)
        
    @transaction.atomic
    def transfer_all_artists(self):
        used_slugs = set()
        
        ArtistV1Link.objects.bulk_create([
            self.transfer_artist(artist_id, used_slugs)
            for (artist_id,) in self.model.query("select id from artists")
        ])
        
        self.new_artist_ids.update()
        
    #
    
    def get_release_type(self, release_type_str):
        """Translates the strings taken directly from the MusicBrainz API
           (which they were stored as in the old DB) into the new enum."""
        
        try:
            return {
                "Album": ReleaseType.ALBUM,
                "Single": ReleaseType.SINGLE,
                "EP": ReleaseType.EP,
                "Broadcast": ReleaseType.BROADCAST,
                "Other": ReleaseType.OTHER,
                "Compilation": ReleaseType.COMPILATION,
                "Soundtrack": ReleaseType.SOUNDTRACK,
                "Spokenword": ReleaseType.SPOKENWORD,
                "Interview": ReleaseType.INTERVIEW,
                "Audiobook": ReleaseType.AUDIOBOOK,
                "Audio drama": ReleaseType.AUDIO_DRAMA,
                "Live": ReleaseType.LIVE,
                "Remix": ReleaseType.REMIX,
                "DJ-mix": ReleaseType.DJ_MIX,
                "Mixtape/Street": ReleaseType.MIXTAPE_STREET,
                "Demo": ReleaseType.DEMO,
                #In the old DB, releases without a type on MusicBrainz were
                #stored as "Unspecified", not null.
                "Unspecified": None
            }[release_type_str]
        
        except KeyError:
            raise ValueError("Unknown release type string: " + release_type_str)
        
    def transfer_release(
        self, release_id, title, release_type, release_date,
        thumb_art_url, full_art_url, colour_1, colour_2, colour_3,
        used_slugs
    ):
        new_release = Release.objects.create(
            title=title,
            slug=generate_slug_tracked(used_slugs, title),
            type=self.get_release_type(release_type) if release_type else None,
            release_date=release_date,
            art_url_250=thumb_art_url,
            art_url_500=full_art_url,
            art_url_max=full_art_url,
            colour_1=colour_1,
            colour_2=colour_2,
            colour_3=colour_3
        )
        
        if release_id in self.release_mbids:
            #Add an MBLink, if there's no other release linked to this MBID
            mb_link, created = ReleaseMBLink.objects.get_or_create(
                release_group_mbid=self.release_mbids[release_id][1],
                defaults={
                    "release": new_release,
                    "release_mbid": self.release_mbids[release_id][0]
                }
            )

            #If there is, mark that one as a duplicate
            if not created:
                ReleaseDuplication.objects.create(
                    original=mb_link.release, updated=new_release
                )
                
                mb_link.release = new_release
                mb_link.release_mbid = self.release_mbids[release_id][0]
                mb_link.save()
        
        return ReleaseV1Link(release=new_release, old_id=release_id)
    
    @transaction.atomic
    def transfer_all_releases(self):
        used_slugs = set()

        ReleaseV1Link.objects.bulk_create([
            self.transfer_release(*row, used_slugs=used_slugs)
            for row in self.model.query(
                "select releases.id, title, type, date, thumb_art_url, full_art_url,"
                " color1, color2, color3 from releases"
                " left join palettes on releases.id = palettes.id"
            )
        ])
        
        self.new_release_ids.update()
        
        Release.artists.through.objects.bulk_create([
            Release.artists.through(
                release_id=self.new_release_ids.map(release_id),
                artist_id=self.new_artist_ids.map(artist_id)
            )
            for artist_id, release_id in self.model.query(
                "select artist_id, release_id from authorships"
                #Ensure we only work on releases and artists which exist (sadly not guaranteed)
                " join releases on release_id = releases.id join artists on artist_id = artists.id"
            )
        ])
        
        #MusicBrainz links were not stored as MBIDs and must be expanded
        def expand_url(url, name):
            if name == "musicbrainz":
                url = "//musicbrainz.org/release/" + url
                
            return url
            
        ReleaseExternalLink.objects.bulk_create([
            ReleaseExternalLink(
                release_id=self.new_release_ids.map(release_id),
                name=name, url=expand_url(url, name)
            )
            for release_id, name, url in self.model.query(
                "select releases.id, link_types.type, target from links"
                " join link_types on type_id = link_types.id"
                #Only links on releases (which exist)
                " join releases on links.id = releases.id"
            )
        ])
        
        Release.tags.through.objects.bulk_create([
            Release.tags.through(
                tag_id=self.new_tag_ids.map(tag_id),
                release_id=self.new_release_ids.map(object_id)
            )
            for tag_id, object_id in self.model.query(
                "select tag_id, object_id from taggings join releases on object_id = releases.id"
            )
        ])
        
    #
    
    def transfer_track(self, release_id, track_id, title, position, side, runtime):
        new_track = Track.objects.create(
            title=title,
            release_id=self.new_release_ids.map(release_id),
            position=position, side=side,
            runtime=runtime
        )
        
        return TrackV1Link(track=new_track, old_id=track_id)
        
    @transaction.atomic
    def transfer_all_tracks(self):
        TrackV1Link.objects.bulk_create([
            self.transfer_track(release_id, *row)
            for release_id, *row in self.model.query(
                "select release_id, id, title, position, side, runtime from tracks")
        ])
        
        self.new_track_ids.update()
        
    #

    def transfer_action(self, action_id, user_id, object_id, type, creation, is_active):
        type = ActionType(type)
        
        fields = dict(
            user_id=self.new_user_ids.map(user_id),
            creation=datetime.fromtimestamp(creation, timezone.utc)
        )
        
        if type in [ActionType.save, ActionType.listen, ActionType.rate]:
            fields["release_id"] = self.new_release_ids.map(object_id)
        
        if type == ActionType.save:
            new_action = SaveAction.objects.create(**fields)
            
        elif type == ActionType.listen:
            new_action = ListenAction.objects.create(**fields)
            
        elif type == ActionType.rate:
            (rating,) = self.model.query_unique(
                "select rating from ratings where action_id=?", action_id)
            
            new_action = RateAction.objects.create(rating=rating, **fields)
        
        elif type == ActionType.pick:
            new_action = PickAction.objects.create(
                track_id=self.new_track_ids.map(object_id),
                **fields
            )

        else:
            raise ValueError("Unexpected action type: " + type.name)
            
        if is_active:
            new_action.set_as_active()
            
        ActionV1Link.objects.create(action_id=new_action.id, old_id=action_id)
    
    @transaction.atomic
    def transfer_all_actions(self):
        for action_id, user_id, object_id, type, creation, active_action_id in self.model.query(
            "select actions.id, user_id, object_id, type, creation, action_id from actions"
            #A left join selects all actions whether or not they are in active_actions
            " left join active_actions on actions.id = action_id"
            " where type != ?", ActionType.share.value
        ):
            #Action rows without a row in active_actions have been joined to NULL
            is_active = active_action_id is not None
            self.transfer_action(action_id, user_id, object_id, type, creation, is_active)
        
    #
    
    def transfer_database(self, verbose=False):
        if verbose: print("Querying release group MBIDs")
        self.query_release_group_mbids()
        if verbose: print("Transferring users")
        self.transfer_all_users()
        if verbose: print("Transferring tags")
        self.transfer_all_tags()
        if verbose: print("Transferring artists")
        self.transfer_all_artists()
        if verbose: print("Transferring releases")
        self.transfer_all_releases()
        if verbose: print("Transferring tracks")
        self.transfer_all_tracks()
        if verbose: print("Transferring actions")
        self.transfer_all_actions()
