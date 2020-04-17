from collections import defaultdict

from django.http import HttpResponseRedirect
from django.views.generic import DetailView, ListView
from django.views.generic.list import MultipleObjectMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, serializers, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from django.contrib.auth.models import User
from r8music.music.models import Artist, Release, Track, Tag
from r8music.actions.models import (
    SaveAction, ListenAction, RateAction, PickAction,
    ActiveActions, enact, get_paginated_activity_feed
)

class ArtistIndex(ListView):
    model = Artist
    template_name ="artist_index.html"
    paginate_by = 25
    
    def get_queryset(self):
        #Most recently imported artists first
        return Artist.objects.order_by("-id")
    
class AbstractArtistPage(DetailView):
    model = Artist
    
    def get_object(self):
        return get_object_or_404(Artist, slug=self.kwargs["slug"])
        
class ArtistMainPage(AbstractArtistPage):
    template_name = "artist_main.html"

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
        user_ratings = self.get_user_ratings(context["artist"])
        context["get_user_rating"] = lambda release: user_ratings[release.id]
        return context

class ArtistActivityPage(AbstractArtistPage):
    template_name = "artist_activity.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        page_no = self.request.GET.get("page")
        artist = context["artist"]
        
        context["activity"], context["page_obj"] = get_paginated_activity_feed(
            lambda release_actions: release_actions.filter(release__artists=artist),
            #Exclude actions on tracks
            lambda track_actions: track_actions.filter(pk=None),
            paginate_by=20, page_no=page_no
        )
        
        return context

# Releases

class AbstractReleasePage(DetailView):
    model = Release
    
    def get_object(self):
        return get_object_or_404(
            Release.objects.prefetch_related("artists"),
            slug=self.kwargs["slug"])
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["accent_color_1"], context["accent_color_2"], context["accent_color_3"] \
            = context["release"].palette
        return context

class ReleaseMainPage(AbstractReleasePage):
    template_name = "release_main.html"
    
    def get_user_actions(self, user, release):
        try:
            active_actions = user.active_actions.select_related("rate").get(release=release)
            picks = active_actions.picked_tracks() if active_actions else []
            return active_actions, picks
            
        except (AttributeError, ActiveActions.DoesNotExist):
            return None, []
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        track_info = self.get_object().tracks_extra()
        track_info["tracks"] = \
            [TrackSerializer(track).data for track in track_info["tracks"]]
        context["track_info"] = track_info
        
        context["user_actions"], context["picks"] \
            = self.get_user_actions(self.request.user, context["release"])
        context["comparison_user"] \
            = User.objects.filter(username=self.request.GET.get("compare")).first()
        _, context["comparison_picks"] \
            = self.get_user_actions(context["comparison_user"], context["release"])
        
        return context

class ReleaseActivityPage(AbstractReleasePage):
    template_name = "release_activity.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        page_no = self.request.GET.get("page")
        release = context["release"]
        
        context["activity"], context["page_obj"] = get_paginated_activity_feed(
            lambda release_actions: release_actions.filter(release=release),
            #Exclude actions on tracks
            lambda track_actions: track_actions.filter(pk=None),
            paginate_by=20, page_no=page_no
        )
        
        return context

class EditReleasePage(LoginRequiredMixin, AbstractReleasePage):
    template_name = "edit_release.html"
    
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
        enact(SaveAction.objects.create(release=self.get_object(), user=request.user))
        return Response({})
        
    @action(detail=True, methods=["post"])
    def listen(self, request, pk=None):
        enact(ListenAction.objects.create(release=self.get_object(), user=request.user))
        return Response({})
        
    @action(detail=True, methods=["post"])
    def rate(self, request, pk=None):
        release = self.get_object()
        rating = request.data.get("rating")
        
        if not rating:
            return Response({"error": "No rating given"}, status=status.HTTP_400_BAD_REQUEST)
            
        else:
            enact(RateAction.objects.create(release=release, user=request.user, rating=rating))
            return Response({"averageRating": release.average_rating()})
        
    def set_release_actions(self, **changes):
        return self.get_object().active_actions \
            .update_or_create(user=self.request.user, defaults=changes)[0]
        
    @action(detail=True, methods=["post"])
    def unsave(self, request, pk=None):
        self.set_release_actions(save_action=None)
        return Response({})
        
    @action(detail=True, methods=["post"])
    def unlisten(self, request, pk=None):
        self.set_release_actions(listen=None)
        return Response({})
        
    @action(detail=True, methods=["post"])
    def unrate(self, request, pk=None):
        self.set_release_actions(rate=None)
        return Response({})

class TrackSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField()
    runtime_str = serializers.CharField()

class TrackViewSet(viewsets.ModelViewSet):
    queryset = Track.objects.all()
    serializer_class = NullSerializer
    permission_classes = (permissions.IsAuthenticated,)
    
    @action(detail=True, methods=["post"])
    def pick(self, request, pk=None):
        enact(PickAction.objects.create(track=self.get_object(), user=request.user))
        return Response({})
        
    @action(detail=True, methods=["post"])
    def unpick(self, request, pk=None):
        request.user.active_actions \
            .get_or_create(release=self.get_object().release)[0] \
            .picks.filter(track=self.get_object()).delete()
        return Response({})

#

class TagPage(DetailView, MultipleObjectMixin):
    model = Tag
    template_name = "tag.html"
    paginate_by = 30
    
    def get_context_data(self, **kwargs):
        releases = self.object.releases.order_by_average_rating()
        return super().get_context_data(object_list=releases, **kwargs)
