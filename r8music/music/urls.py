from django.conf.urls import url
from django.urls import path, reverse

from .views import ArtistIndex, ArtistMainPage, ReleaseMainPage, EditReleasePage, TagPage

null_view = lambda: None

urlpatterns = [
    path("artists", ArtistIndex.as_view(), name="artist_index"),
    path("artist/<slug>", ArtistMainPage.as_view(), name="artist"),
    path("artist/<slug>/activity", null_view, name="artist_activity"),
    
    path("release/<slug>", ReleaseMainPage.as_view(), name="release"),
    path("release/<slug>/activity", null_view, name="release_activity"),
    path("release/<slug>/edit", EditReleasePage.as_view(), name="edit_release"),
    
    path("tag/<int:pk>", TagPage.as_view(), name="tag"),
]

#Functions to produce URLs from model instances, available in templates

def url_for_artist(artist, route="artist"):
    return reverse(route, args=[artist.slug])

def url_for_release(release, route="release"):
    return reverse(route, args=[release.slug])
    
def url_for_tag(tag):
    return reverse("tag", args=[tag.id])
    
urlreversers = [
    url_for_artist, url_for_release, url_for_tag
]
