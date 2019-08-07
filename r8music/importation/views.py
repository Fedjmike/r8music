import musicbrainzngs

from django.views.generic import TemplateView, DetailView
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from background_task import background

from r8music.music.models import Artist
from r8music.music.urls import url_for_artist
from .importer import Importer

def search_artists(query):
    musicbrainzngs.set_useragent("Skiller", "0.0.0", "mb@satyarth.me")
    return musicbrainzngs.search_artists(artist=query)["artist-list"]

@background
def schedule_import_artist(artist_mbid):
    Importer().import_artist(artist_mbid)

class ImportArtistPage(TemplateView):
    """Displays the artist search form after a GET, and imports an artist given in a POST"""
    
    template_name = "import_artist.html"
    
    def post(self, request):
        artist_mbid = request.POST.get("artist-mbid")
        
        if not artist_mbid:
            messages.add_message(
                request, messages.ERROR,
                request.path + " requires an 'artist-mbid' parameter")
            return redirect(reverse("import_artist"))
            
        schedule_import_artist(artist_mbid)
        messages.add_message(request, messages.SUCCESS, "The artist will be added soon")
        
        return redirect(reverse("artist_index"))
        
class ImportArtistSearchResults(TemplateView):
    """Displays the importation options from a search of MusicBrainz"""
    
    template_name =  "import_artist_search_results.html"
    
    def get_context_data(self, **kwargs):
        artist_name = self.request.GET.get("name")
        
        mb_results = search_artists(artist_name)
        
        results = [
            {
                "mbid": result["id"],
                "name": result["name"],
                "disambiguation":
                    result["disambiguation"] if "disambiguation" in result
                    else result["area"]["name"] if "area" in result
                    else None
            }
            for result in mb_results
        ]
        
        return super().get_context_data(query=artist_name, results=results, **kwargs)
        
class UpdateArtist(DetailView):
    model = Artist
    
    def get(self, request, id):
        artist = get_object_or_404(Artist, id=id)
        schedule_import_artist(artist.mb_link.mbid)
        
        messages.add_message(request, messages.SUCCESS, "The artist will be updated soon")
        return redirect(url_for_artist(artist))
