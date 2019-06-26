from collections import defaultdict

from django.http import HttpResponseRedirect
from django.views.generic import DetailView, ListView
from django.views.generic.list import MultipleObjectMixin

from rest_framework import viewsets, serializers, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from r8music.music.models import Artist, Release, Track, Tag
from r8music.actions.models import SaveAction, ListenAction, RateAction, PickAction, ActiveActions

class ArtistIndex(ListView):
    model = Artist
    template_name ="artist_index.html"
    paginate_by = 25
    
    def get_queryset(self):
        #Most recently imported artists first
        return Artist.objects.order_by("-id")
    
class ArtistMainPage(DetailView):
    model = Artist
    template_name ="artist_main.html"
    
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

# Releases

class AbstractReleasePage(DetailView):
    model = Release
    
    def get_object(self):
        return Release.objects.prefetch_related("artists").get(slug=self.kwargs["slug"])
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        colours = context["release"].palette
        context["accent_color_1"], context["accent_color_2"], context["accent_color_3"] = colours
        
        return context

class ReleaseMainPage(AbstractReleasePage):
    template_name = "release_main.html"
    
    def get_user_actions(self, release):
        try:
            return self.request.user.active_actions.select_related("rate").get(release=release)
            
        except (AttributeError, ActiveActions.DoesNotExist):
            return None
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user_actions"] = self.get_user_actions(context["release"])
        return context

class EditReleasePage(AbstractReleasePage):
    template_name ="edit_release.html"
    
    def post(self, request, *args, **kwargs):
        colours = (request.POST.get(c) for c in ["colour-1", "colour-2", "colour-3"])
        
        release = self.get_object()
        release.set_palette(*colours)
        
        #Redirect back to the edit page
        return HttpResponseRedirect(request.path_info)

# Release and track APIs

class NullSerializer(serializers.Serializer):
    pass

class ReleaseViewSet(viewsets.ModelViewSet):
    queryset = Release.objects.all()
    serializer_class = NullSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    @action(detail=True, methods=["post"])
    def save(self, request, pk=None):
        SaveAction.objects.create(
            release=self.get_object(), user=request.user
        ).set_as_active()
        
        return Response()
        
    @action(detail=True, methods=["post"])
    def listen(self, request, pk=None):
        ListenAction.objects.create(
            release=self.get_object(), user=request.user
        ).set_as_active()
        
        return Response()
        
    @action(detail=True, methods=["post"])
    def rate(self, request, pk=None):
        release = self.get_object()
        rating = request.data.get("rating")
        
        if not rating:
            return Response({"error": "No rating given"}, status=status.HTTP_400_BAD_REQUEST)
            
        else:
            RateAction.objects.create(
                release=release, user=request.user, rating=rating
            ).set_as_active()
                        
            return Response({"averageRating": release.average_rating()})
        
    def _get_active_actions(self, request):
        return self.get_object().active_actions.get_or_create(user=request.user)[0]
        
    @action(detail=True, methods=["post"])
    def unsave(self, request, pk=None):
        aa = self._get_active_actions(request)
        aa.save_action = None
        aa.save()
        
        return Response()
        
    @action(detail=True, methods=["post"])
    def unlisten(self, request, pk=None):
        aa = self._get_active_actions(request)
        aa.listen = None
        aa.save()
        
        return Response()
        
    @action(detail=True, methods=["post"])
    def unrate(self, request, pk=None):
        aa = self._get_active_actions(request)
        aa.rate = None
        aa.save()
        
        return Response()

class TrackViewSet(viewsets.ModelViewSet):
    queryset = Track.objects.all()
    serializer_class = NullSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    @action(detail=True, methods=["post"])
    def pick(self, request, pk=None):
        PickAction.objects.create(
            track=self.get_object(), user=request.user
        ).set_as_active()
        
        return Response()
        
    @action(detail=True, methods=["post"])
    def unpick(self, request, pk=None):   
        track = self.get_object()
        aa = track.release.active_actions.get_or_create(user=request.user)[0]
        aa.picks.filter(track=track).delete()
        
        return Response()

#

class TagPage(DetailView, MultipleObjectMixin):
    model = Tag
    template_name = "tag.html"
    paginate_by = 30
    
    def get_context_data(self, **kwargs):
        releases = self.object.releases.order_by_average_rating().all()
        return super().get_context_data(object_list=releases, **kwargs)
