from django.conf.urls import url
from django.urls import path, reverse

from .views import ArtistIndex, ArtistPage, ReleasePage

null_view = lambda: None

urlpatterns = [
    path("artists", ArtistIndex.as_view(), name="artist_index"),
    path("tag/<int:pk>", null_view, name="tag"),
    path("artist/<slug>", ArtistPage.as_view(), name="artist"),
    path("release/<slug>", ReleasePage.as_view(), name="release"),
]

#Functions to produce URLs from model instances, available in templates

def url_for_artist(artist):
    return reverse("artist", args=[artist.slug])

def url_for_release(release):
    return reverse("release", args=[release.slug])
    
def url_for_tag(tag):
    return reverse("tag", args=[tag.id])
    
urlreversers = [
    url_for_artist, url_for_release, url_for_tag
]
