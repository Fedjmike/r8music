from django.conf.urls import url
from django.urls import path, reverse

null_view = lambda: None

urlpatterns = [
    path("artists", null_view, name="artist_index"),
    path("tag/<int:pk>", null_view, name="tag"),
    path("<slug>", null_view, name="artist"),
    path("<slug:artist_slug>/<slug:release_slug>", null_view, name="release"),
]
