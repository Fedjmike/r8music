from django.contrib import admin
from .models import Artist, Release, Track, ArtistExternalLink, ReleaseExternalLink, Tag

admin.site.register([Artist, Release, Track, ArtistExternalLink, ReleaseExternalLink, Tag])
