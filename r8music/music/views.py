from collections import defaultdict

#from django.shortcuts import render
from django.views.generic import DetailView

from .models import Artist, Release
from r8music.actions.models import ActiveActions

class ArtistPage(DetailView):
    model = Artist
    template_name ="artist.html"
    
    def get_object(self):
        return Artist.objects.get(slug=self.kwargs["slug"])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user_ratings = ActiveActions.objects \
            .filter(release__artists=context["artist"], user=self.request.user) \
            .ratings()
            
        context["user_ratings"] = defaultdict(lambda: None, user_ratings)
        return context
    
class ReleasePage(DetailView):
    model = Release
    template_name ="release.html"
    
    def get_object(self):
        return Release.objects.prefetch_related("artists").get(slug=self.kwargs["release_slug"], artists__slug=self.kwargs["artist_slug"])
