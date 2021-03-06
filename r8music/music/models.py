from itertools import count
from unidecode import unidecode

from django.db import models
from django.db.models import Count, Avg, Q, F
from django_enumfield import enum

from django.template.defaultfilters import slugify

from django.contrib.auth.models import User

def generate_slug(is_free, name):
    slug = slugify(unidecode(name))
    only_index = not slug
    candidates = ("%s-%d" % (slug, n) if n or only_index else slug for n in count(0))
    return next(filter(is_free, candidates))
    
def generate_slug_tracked(used_slugs, name):
    """Generates a slug, using a set of slugs already used. This is to avoid
       the many slow queries otherwise required. Updates the given set in place."""
    is_free = lambda slug: slug not in used_slugs
    slug = generate_slug(is_free, name)
    used_slugs.add(slug)
    return slug

def make_runtime_str(milliseconds):
    return "%d:%02d" % (milliseconds//60000, (milliseconds/1000) % 60)

#

class TagQuerySet(models.QuerySet):
    def order_by_frequency(self):
        return self.annotate(frequency=Count("releases")).order_by("-frequency")

    def frequencies(self):
        return dict(
            self.annotate(frequency=Count("releases"))
                .values_list("id", "frequency")
        )

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
    
    image_url = models.TextField(null=True)
    image_thumb_url = models.TextField(null=True)
    
    @property
    def all_tracks(self):
        return Track.objects.filter(release__artists=self)
    
    @property
    def all_tags(self):
        return Tag.objects.filter(releases__artists=self)
        
    @property
    def wikipedia_url(self):
        try:
            return self.external_links.filter(name="Wikipedia").get().url

        except ArtistExternalLink.DoesNotExist:
            return None

    def is_partially_imported(self):
        solo_releases = Release.objects.annotate(artist_no=Count("artists")) \
            .filter(artist_no=1, artists=self)
        return solo_releases.count() == 0
    
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
        
    def rated_by_user(self, user):
        return self.filter(active_actions__user=user) \
            .annotate(rating_by_user=F("active_actions__rate__rating")) \
            .exclude(rating_by_user=None)
            
    def with_actions_by_user(self, user):
        return self.filter(active_actions__user=user) \
            .annotate(
                save=F("active_actions__save_action"),
                listen=F("active_actions__listen"),
                rate=F("active_actions__rate")
            )
        
    def listened_unrated_by_user(self, user):
        return self.with_actions_by_user(user) \
            .filter(rate=None).exclude(listen=None) \
            .annotate(listen_timestamp=F("active_actions__listen__creation"))
    
    def saved_by_user(self, user):
        return self.with_actions_by_user(user) \
            .exclude(save=None) \
            .annotate(save_timestamp=F("active_actions__save_action__creation"))
        
class Release(models.Model):
    title = models.TextField()
    slug = models.TextField(unique=True)
    
    artists = models.ManyToManyField(Artist, related_name="releases")
    
    type = enum.EnumField(ReleaseType, null=True, default=None)
    #As an ISO8601 date string, or a fragment (e.g. YYYY) in case the full date is unknown
    release_date = models.TextField(null=True)
    
    tags = models.ManyToManyField(Tag, related_name="releases")
    
    #Cover art URLs (in different dimensions)
    art_url_250 = models.TextField(null=True)
    art_url_500 = models.TextField(null=True)
    art_url_max = models.TextField(null=True)
    
    #The colour palette used on the release page, expressed as HTML RGB codes (#rrggbb),
    #derived from the album art
    colour_1 = models.TextField(null=True)
    colour_2 = models.TextField(null=True)
    colour_3 = models.TextField(null=True)
    
    objects = ReleaseQuerySet.as_manager()
    
    class Meta:
        ordering = ["release_date"]
    
    @property
    def is_album(self):
        return self.type == ReleaseType.ALBUM
    
    @property
    def release_year_str(self):
        return self.release_date[:4] if self.release_date else None
    
    @property
    def palette(self):
        return self.colour_1, self.colour_2, self.colour_3
        
    def set_palette(self, *colours):
        self.colour_1, self.colour_2, self.colour_3 = colours
        self.save()
    
    def average_rating(self):
        return self.active_actions.aggregate(average=Avg("rate__rating"))["average"]
    
    def tracks_extra(self):
        tracks = self.tracks.all()
        return {
            "tracks": tracks,
            "runtime": make_runtime_str(sum(track.runtime for track in tracks if track.runtime)),
        }

class TrackQuerySet(models.QuerySet):
    def order_by_popularity(self):
        is_picked = Q(release__active_actions__picks__track_id=F("id"))
        return self.annotate(popularity=Count(1, filter=is_picked)).order_by("-popularity")
        
class Track(models.Model):
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="tracks")
    
    title = models.TextField()
    
    side = models.IntegerField()
    #The position within the indicated side (not overall)
    position = models.IntegerField()
    
    #In miliseconds
    runtime = models.IntegerField(null=True)
    
    objects = TrackQuerySet.as_manager()
    
    class Meta:
        ordering = ["side", "position"]
    
    @property
    def runtime_str(self):
        return make_runtime_str(self.runtime) if self.runtime else None

#

class ExternalLinkQuerySet(models.QuerySet):
    def from_sites(self, site_names):
        """Returns a sequence of (site, link) for all links with matching website
           names (case-insensitive), in the order they were given."""
        
        all_links_by_name = {link.name.lower(): link for link in self.all()}
        
        for site_name in site_names:
            try:
                yield (site_name, all_links_by_name[site_name.lower()])
                
            except KeyError:
                pass

class ExternalLink(models.Model):
    """A link to a page on an external site"""
    
    url = models.TextField()
    #Identifies the link, for example, by the name of the external website
    name = models.TextField()
    
    objects = ExternalLinkQuerySet.as_manager()
    
    class Meta:
        abstract = True
    
class ArtistExternalLink(ExternalLink):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="external_links")
    
class ReleaseExternalLink(ExternalLink):
    release = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="external_links")
