from django.conf.urls import url
from django.urls import path, reverse

from .views import ArtistPage, ReleasePage

null_view = lambda: None

urlpatterns = [
    path("artists", null_view, name="artist_index"),
    path("tag/<int:pk>", null_view, name="tag"),
    path("<slug>", ArtistPage.as_view(), name="artist"),
    path("<slug:artist_slug>/<slug:release_slug>", ReleasePage.as_view(), name="release"),
]

#Functions to produce URLs from model instances, available in templates

def url_for_artist(artist):
    return reverse("artist", args=[artist.slug])

def url_for_release(release):
    primary_artist = release.artists.values("slug")[0]
    return reverse("release", kwargs={
        "artist_slug": primary_artist["slug"], "release_slug": release.slug
    })
    
def url_for_tag(tag):
    return reverse("tag", args=[tag.id])
    
urlreversers = [
    url_for_artist, url_for_release, url_for_tag
]
