import musicbrainzngs

from django.conf import settings
from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages

from r8music.music.models import Artist
from r8music.music.urls import url_for_artist
from .models import ArtistMBLink
from .importer import schedule_import_artist

def search_artists(query):
    musicbrainzngs.set_useragent(*settings.MUSICBRAINZ_USERAGENT)
    return musicbrainzngs.search_artists(artist=query)["artist-list"]

class ImportArtistPage(LoginRequiredMixin, TemplateView):
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
        
class ImportArtistSearchResults(LoginRequiredMixin, TemplateView):
    """Displays the importation options from a search of MusicBrainz"""
    
    template_name = "import_artist_search_results.html"
    
    def get_context_data(self, **kwargs):
        artist_name = self.request.GET.get("name")
        
        mb_results = search_artists(artist_name)
        
        already_imported_mbids = set(
            ArtistMBLink.objects
                .filter(mbid__in=[result["id"] for result in mb_results])
                .values_list("mbid", flat=True)
        )
        
        results = [
            {
                "mbid": result["id"],
                "name": result["name"],
                "already_imported_artist":
                    ArtistMBLink.objects.get(mbid=result["id"]).artist
                    if result["id"] in already_imported_mbids else None,
                "disambiguation":
                    result.get("disambiguation")
                    or (result["area"]["name"] if "area" in result else None)
            }
            for result in mb_results
        ]
        
        return super().get_context_data(query=artist_name, results=results, **kwargs)
        
class UpdateArtist(LoginRequiredMixin, DetailView):
    model = Artist
    
    def get(self, request, id):
        artist = get_object_or_404(Artist, id=id)
        schedule_import_artist(artist.mb_link.mbid)
        
        messages.add_message(request, messages.SUCCESS, "The artist will be updated soon")
        return redirect(url_for_artist(artist))
