from itertools import groupby
from collections import Counter

from django.views.generic import DetailView
from django.views.generic.base import TemplateResponseMixin

from django.db.models import Count, Q

from django.contrib.auth.models import User
from r8music.music.models import Release

class UserMainPage(DetailView, TemplateResponseMixin):
    model = User
    template_name = "user_main.html"
    
    def get_object(self):
        return User.objects.get(username=self.kwargs.get("slug"))
        
    def get_actions_counts(self, user):
        """Return the number of releases interacted with in certain ways by a user."""
        return user.active_actions.aggregate(
            rated=Count("id", filter=~Q(rate=None)),
            listened_unrated=Count("id", filter=~Q(listen=None) & Q(rate=None)),
            saved=Count("id", filter=~Q(save=None))
        )
        
    def get_releases_rated_groups(self, user):
        """Return the releases rated by a user, grouped by rating, as list of tuples,
           [(rating, rating_description, [releases])], where rating_description is the
           heading given by the user for that rating group."""
        
        releases_rated = Release.objects \
            .rated_by_user(user) \
            .order_by("-rating_by_user", "artists__name", "release_date") \
            .prefetch_related("artists")
        
        descriptions = {desc.rating: desc.description for desc in user.profile.rating_descriptions.all()}
        
        return [
            (rating, descriptions.get(rating, None), list(releases))
            for rating, releases in groupby(releases_rated, lambda r: r.rating_by_user)
        ]
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_counts"] = self.get_actions_counts(context["user"])
        context["releases_rated_groups"] = self.get_releases_rated_groups(context["user"])
        return context
