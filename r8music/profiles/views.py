from itertools import groupby
from collections import Counter

from django.views.generic import DetailView, ListView
from rest_framework.decorators import api_view
from rest_framework.response import Response

from django.db.models import Count, Q

from django.contrib.auth.models import User
from r8music.profiles.models import UserRatingDescription
from r8music.music.models import Release

class UserIndex(ListView):
    model = User
    template_name = "user_index.html"
    paginate_by = 25
    
    def get_queryset(self):
        return User.objects.order_by("id")

#

class AbstractUserPage(DetailView):
    model = User
    
    def get_object(self):
        return User.objects.get(username=self.kwargs.get("slug"))
        
    def get_actions_counts(self, user):
        """Return the number of releases interacted with in certain ways by a user."""
        return user.active_actions.aggregate(
            rated=Count("id", filter=~Q(rate=None)),
            listened_unrated=Count("id", filter=~Q(listen=None) & Q(rate=None)),
            saved=Count("id", filter=~Q(save_action=None))
        )
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_counts"] = self.get_actions_counts(context["user"])
        return context
        
class UserMainPage(AbstractUserPage):
    template_name = "user_main.html"
    
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
        context["releases_rated_groups"] = self.get_releases_rated_groups(context["user"])
        return context

class UserListenedUnratedPage(AbstractUserPage):
    template_name = "user_listened_unrated.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["listened_unrated"] = Release.objects.listened_unrated_by_user(context["user"])
        return context

class UserSavedPage(AbstractUserPage):
    template_name = "user_saved.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["saved"] = Release.objects.saved_by_user(context["user"])
        return context

class UserFriendsPage(AbstractUserPage):
    template_name = "user_friends.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["friends"] = context["user"].profile.friendships()
        return context

class UserStatsPage(AbstractUserPage):
    template_name = "user_stats.html"
    
    def get_rating_counts(self, user):
        """Return counts of releases given each rating by a user."""
        
        rating_counts = user.active_actions.aggregate(**{
            ("rated_%d" % n): Count("id", filter=Q(rate__rating=n))
            for n in range(1, 8+1)
        })
        
        return [rating_counts["rated_%d" % n] for n in range(1, 8+1)]
        
        
    def get_release_year_counts(self, user):
        """Return counts of releases listened to by a user for each year between
           the years of the earliest and latest releases, as ([years], [counts])."""
        
        release_dates = user.active_actions \
            .exclude(listen=None) \
            .order_by("release__release_date") \
            .values_list("release__release_date", flat=True)
        release_years = [int(date[:4]) for date in release_dates]
        
        year_counts = Counter(release_years)
        
        range_of = lambda iterable: \
            range(min(iterable), max(iterable)+1) if iterable else []
        year_range = list(range_of(list(year_counts.keys())))
        
        return (year_range, [year_counts.get(year, 0) for year in year_range])
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rating_counts"] = self.get_rating_counts(context["user"])
        context["release_year_counts"] = self.get_release_year_counts(context["user"])
        return context

# User API

@api_view(["post"])
def rating_description(request):
    try:
        rating = int(request.data.get("rating"))
        description = request.data.get("description")

    except ValueError:
        return Response({"error": "Rating not provided, or not an integer"}, status=status.HTTP_400_BAD_REQUEST)
        
    if not description:
        return Response({"error": "Description not provided"}, status=status.HTTP_400_BAD_REQUEST)
        
    else:
        rd, _ = UserRatingDescription.objects.get_or_create(user=request.user.profile, rating=rating)
        rd.description = description
        rd.save()
        
        return Response()
