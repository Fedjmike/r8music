from itertools import count, groupby

from django.db import models
from django_enumfield import enum
from django.db.models import Avg

from django.template.defaultfilters import slugify

from r8music.profiles.models import User

def runtime_str(milliseconds):
    return "%d:%02d" % (milliseconds//60000, (milliseconds/1000) % 60)

#

class Tag(models.Model):
    name = models.TextField()
    title = models.TextField()
    description = models.TextField()
    
    owner = models.ForeignKey(User, on_delete=models.PROTECT, null=True)

class DiscogsTag(Tag):
    discogs_name = models.TextField()

#

class Artist(models.Model):
    name = models.TextField()
    slug = models.TextField()
    #A couple of sentences or short paragraphs about the artist
    description = models.TextField(null=True)
    
    def wikipedia_urls(self):
        return None
    
class ReleaseType(enum.Enum):
    ALBUM = 1
    SINGLE = 2
    EP = 3
    BROADCAST = 4
    OTHER = 7
    #
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

class ReleaseQuerySet(models.QuerySet):
    def albums(self):
        return self.filter(type=ReleaseType.ALBUM)
        
    def non_albums(self):
        return self.exclude(type=ReleaseType.ALBUM)
        
class Release(models.Model):
    title = models.TextField()
    slug = models.SlugField(unique=True)
    artists = models.ManyToManyField(Artist, related_name="releases")
    type = enum.EnumField(ReleaseType, null=True, default=None)
    release_date = models.TextField()
    
    tags = models.ManyToManyField(Tag, related_name="releases")
    
    #Cover art links
    art_url_250 = models.TextField(null=True)
    art_url_500 = models.TextField(null=True)
    art_url_max = models.TextField(null=True)
    
    #The colour palette used on the release page, derived from the album art
    colour1 = models.TextField(null=True)
    colour2 = models.TextField(null=True)
    colour3 = models.TextField(null=True)
    
    objects = ReleaseQuerySet.as_manager()
    
    def release_year_str(self):
        return self.release_date[:4]
    
    def palette(self):
        return self.colour1, self.colour2, self.colour3
    
    def average_rating(self):
        return self.active_actions.aggregate(average=Avg("rate__rating"))["average"]
    
    def tracks_extra(self):
        tracks = self.tracks.all()
        return {
            "sides": [list(tracks) for _, tracks in groupby(tracks, lambda track: track.side)],
            "runtime": runtime_str(sum(track.runtime for track in tracks if track.runtime)),
            "track_no": len(tracks)
        }

class Track(models.Model):
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="tracks")
    
    title = models.TextField()
    slug = models.SlugField(unique=True)
    position = models.IntegerField()
    side = models.IntegerField()
    #In miliseconds
    runtime = models.IntegerField(null=True)
    
    def runtime_str(self):
        return runtime_str(self.runtime) if self.runtime else None

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

#

def generate_slug(is_free, name):
    slug = slugify(name)
    candidates = ("%s-%d" % (slug, n) if n else slug for n in count(0))
    return next(filter(is_free, candidates))
