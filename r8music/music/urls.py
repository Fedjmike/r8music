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
