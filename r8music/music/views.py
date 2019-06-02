from collections import defaultdict

from django.views.generic import DetailView

from .models import Artist, Release
from r8music.actions.models import ActiveActions

class ArtistPage(DetailView):
    model = Artist
    template_name ="artist.html"
    
    def get_object(self):
        return Artist.objects.get(slug=self.kwargs["slug"])

    def get_user_ratings(self, artist, user):
        user_ratings = {
            id: user_rating for id, user_rating
            in ActiveActions.objects
                .filter(release__artists=artist, user=user).exclude(rate=None)
                .values_list("release_id", "rate__rating")
        }
        
        return defaultdict(lambda: None, user_ratings)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_ratings"] = self.get_user_ratings(context["artist"], self.request.user)
        return context
    
class ReleasePage(DetailView):
    model = Release
    template_name ="release.html"
    
    def get_object(self):
        return Release.objects.prefetch_related("artists").get(slug=self.kwargs["release_slug"], artists__slug=self.kwargs["artist_slug"])
