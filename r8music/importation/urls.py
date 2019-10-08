from django.urls import path

from .views import ImportArtistPage, ImportArtistSearchResults, UpdateArtist

urlpatterns = [
    path("import-artist", ImportArtistPage.as_view(), name="import_artist"),
    path("import-artist/search", ImportArtistSearchResults.as_view(), name="import_artist_search"),
    path("update-artist/<int:id>", UpdateArtist.as_view(), name="update_artist"),
]
