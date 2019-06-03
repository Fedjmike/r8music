from collections import defaultdict

from django.views.generic import DetailView, ListView
from django.views.generic.list import MultipleObjectMixin

from .models import Artist, Release, Tag
from r8music.actions.models import ActiveActions

class ArtistIndex(ListView):
    model = Artist
    template_name ="artist_index.html"
    paginate_by = 25
    
    def get_queryset(self):
        #Most recently imported artists first
        return Artist.objects.order_by("-id")
    
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
        return Release.objects.prefetch_related("artists").get(slug=self.kwargs["slug"])

class TagPage(DetailView, MultipleObjectMixin):
    model = Tag
    template_name = "tag.html"
    paginate_by = 30
    
    def get_context_data(self, **kwargs):
        releases = self.object.releases.order_by_average_rating().all()
        return super().get_context_data(object_list=releases, **kwargs)
