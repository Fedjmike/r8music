from collections import defaultdict

from django.http import HttpResponseRedirect
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

    def get_user_ratings(self, artist):
        #A defaultdict allows the template to look up a release whether or not there is a rating
        user_ratings = defaultdict(lambda: None)
        
        if not self.request.user.is_anonymous:
            user_ratings.update({
                id: user_rating for id, user_rating
                in ActiveActions.objects
                    .filter(release__artists=artist, user=self.request.user).exclude(rate=None)
                    .values_list("release_id", "rate__rating")
            })
        
        return user_ratings
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_ratings"] = self.get_user_ratings(context["artist"])
        return context

#

def set_page_palette(context):
    colours = context["release"].palette
    context["accent_color_1"], context["accent_color_2"], context["accent_color_3"] = colours

class ReleasePage(DetailView):
    model = Release
    template_name ="release.html"
    
    def get_object(self):
        return Release.objects.prefetch_related("artists").get(slug=self.kwargs["slug"])
        
    def get_user_actions(self, release):
        try:
            return self.request.user.active_actions.select_related("rate").get(release=release)
            
        except (AttributeError, ActiveActions.DoesNotExist):
            return None
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_actions"] = self.get_user_actions(context["release"])
        set_page_palette(context)
        return context

class EditReleasePage(DetailView):
    model = Release
    template_name ="edit_release.html"
    
    def get_object(self):
        return Release.objects.prefetch_related("artists").get(slug=self.kwargs["slug"])
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        set_page_palette(context)
        return context
        
    def post(self, request, *args, **kwargs):
        colours = (request.POST.get(c) for c in ["colour-1", "colour-2", "colour-3"])
        
        release = self.get_object()
        release.set_palette(*colours)
        
        #Redirect back to the edit page
        return HttpResponseRedirect(request.path_info)

#

class TagPage(DetailView, MultipleObjectMixin):
    model = Tag
    template_name = "tag.html"
    paginate_by = 30
    
    def get_context_data(self, **kwargs):
        releases = self.object.releases.order_by_average_rating().all()
        return super().get_context_data(object_list=releases, **kwargs)
