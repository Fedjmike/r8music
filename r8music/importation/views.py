import musicbrainzngs

from django.views.generic import DetailView
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from background_task import background

from r8music.music.models import Artist
from r8music.music.urls import url_for_artist
from .importer import Importer

@background
def schedule_import_artist(artist_mbid):
    Importer().import_artist(artist_mbid)

class UpdateArtist(DetailView):
    model = Artist
    
    def post(self, request, id):
        artist = get_object_or_404(Artist, id=id)
        schedule_import_artist(artist.mb_link.mbid)
        
        messages.add_message(request, messages.SUCCESS, "The artist will be updated soon")
        return redirect(url_for_artist(artist))
