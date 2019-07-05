from django.conf.urls import url
from django.urls import path

from .views import GeneralSearchPage, ArtistSearchPage, ReleaseSearchPage

urlpatterns = [
    path("search", GeneralSearchPage.as_view(), name="search"),
    path("search/artists", ArtistSearchPage.as_view(), name="artist_search"),
    path("search/releases", ReleaseSearchPage.as_view(), name="release_search"),
]
