from itertools import count

from django.db import models
from django_enumfield import enum
from django.template.defaultfilters import slugify

from r8music.profiles.models import User

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
    
class Track(models.Model):
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="tracks")
    
    title = models.TextField()
    slug = models.SlugField(unique=True)
    position = models.IntegerField()
    side = models.IntegerField()
    #In miliseconds
    runtime = models.IntegerField(null=True)

#

class ExternalLink(models.Model):
    """A link to a page on an external site"""
    
    url = models.TextField()
    #Identifies the link, for example, by the name of the external website
    name = models.TextField()
    
    class Meta:
        abstract = True
    
class ArtistExternalLink(ExternalLink):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="links")
    
class ReleaseExternalLink(ExternalLink):
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="links")

#

def generate_slug(is_free, name):
    slug = slugify(name)
    candidates = ("%s-%d" % (slug, n) if n else slug for n in count(0))
    return next(filter(is_free, candidates))
