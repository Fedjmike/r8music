from itertools import count, groupby

from django.db import models
from django.db.models import Count, Avg, Q, F
from django_enumfield import enum

from django.template.defaultfilters import slugify

from django.contrib.auth.models import User

def generate_slug(is_free, name):
    slug = slugify(name)
    candidates = ("%s-%d" % (slug, n) if n else slug for n in count(0))
    return next(filter(is_free, candidates))
    
def make_runtime_str(milliseconds):
    return "%d:%02d" % (milliseconds//60000, (milliseconds/1000) % 60)

#

class TagQuerySet(models.QuerySet):
    def order_by_frequency(self):
        return self.annotate(frequency=Count("releases")).order_by("-frequency")

class Tag(models.Model):
    name = models.TextField()
    title = models.TextField()
    description = models.TextField()
    
    owner = models.ForeignKey(User, on_delete=models.PROTECT, null=True)
    
    objects = TagQuerySet.as_manager()

class DiscogsTag(Tag):
    discogs_name = models.TextField()

#

class Artist(models.Model):
    name = models.TextField()
    slug = models.TextField()
    #A couple of sentences or short paragraphs about the artist
    description = models.TextField(null=True)
    
    @property
    def all_tracks(self):
        return Track.objects.filter(release__artists=self)
    
    @property
    def all_tags(self):
        return Tag.objects.filter(releases__artists=self)
         
    @property
    def image(self):
        return None, None
        
    @property
    def wikipedia_url(self):
        return None
    
class ReleaseType(enum.Enum):
    ALBUM = 1
    SINGLE = 2
    EP = 3
    BROADCAST = 4
    COMPILATION = 5
    SOUNDTRACK = 6
    SPOKENWORD = 7
    INTERVIEW = 8
    AUDIOBOOK = 9
    AUDIO_DRAMA = 10
    LIVE = 11
    REMIX = 12
    DJ_MIX = 13
    MIXTAPE_STREET = 14
    DEMO = 15
    OTHER = 16

class ReleaseQuerySet(models.QuerySet):
    def albums(self):
        return self.filter(type=ReleaseType.ALBUM)
        
    def with_average_rating(self):
        return self.annotate(average_rating=Avg("active_actions__rate__rating"))
        
    def order_by_average_rating(self):
        return self.with_average_rating().order_by("-average_rating")
        
    def with_ratings_by_user(self, user):
        return self.annotate(user_rating=F("active_actions__rate__rating")) \
            .filter(active_actions__user=user)
        
class Release(models.Model):
    title = models.TextField()
    slug = models.SlugField(unique=True)
    
    artists = models.ManyToManyField(Artist, related_name="releases")
    
    type = enum.EnumField(ReleaseType, null=True, default=None)
    #As an ISO8601 date string, or a fragment (e.g. YYYY) in case the full date is unknown
    release_date = models.TextField()
    
    tags = models.ManyToManyField(Tag, related_name="releases")
    
    #Cover art URLs (in different dimensions)
    art_url_250 = models.TextField(null=True)
    art_url_500 = models.TextField(null=True)
    art_url_max = models.TextField(null=True)
    
    #The colour palette used on the release page, derived from the album art
    colour_1 = models.TextField(null=True)
    colour_2 = models.TextField(null=True)
    colour_3 = models.TextField(null=True)
    
    objects = ReleaseQuerySet.as_manager()
    
    @property
    def is_album(self):
        return self.type == ReleaseType.ALBUM
    
    @property
    def release_year_str(self):
        return self.release_date[:4]
    
    @property
    def palette(self):
        return self.colour_1, self.colour_2, self.colour_3
    
    def average_rating(self):
        return self.active_actions.aggregate(average=Avg("rate__rating"))["average"]
    
    def tracks_extra(self):
        tracks = self.tracks.all()
        return {
            "sides": [list(tracks) for _, tracks in groupby(tracks, lambda track: track.side)],
            "runtime": make_runtime_str(sum(track.runtime for track in tracks if track.runtime)),
            "track_no": len(tracks)
        }

class TrackQuerySet(models.QuerySet):
    def order_by_popularity(self):
        is_picked = Q(release__active_actions__picks__track_id=F("id"))
        return self.annotate(popularity=Count(1, filter=is_picked)).order_by("-popularity")
        
class Track(models.Model):
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="tracks")
    
    title = models.TextField()
    slug = models.SlugField(unique=True)
    
    side = models.IntegerField()
    #The position within the indicated side, not overall
    position = models.IntegerField()
    
    #In miliseconds
    runtime = models.IntegerField(null=True)
    
    objects = TrackQuerySet.as_manager()
    
    @property
    def runtime_str(self):
        return make_runtime_str(self.runtime) if self.runtime else None

#

class ExternalLink(models.Model):
    """A link to a page on an external site"""
    
    url = models.TextField()
    #Identifies the link, for example, by the name of the external website
    name = models.TextField()
    
    class Meta:
        abstract = True
    
class ArtistExternalLink(ExternalLink):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="external_links")
    
class ReleaseExternalLink(ExternalLink):
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="external_links")
