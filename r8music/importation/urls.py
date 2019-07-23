from django.urls import path

null_view = lambda: None

urlpatterns = [
    path("import-artist", null_view, name="import_artist"),
    path("import-artist/search", null_view, name="import_artist_search"),
    path("update-artist/<int:id>", null_view, name="update_artist"),
]
