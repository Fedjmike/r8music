from django.urls import path

from .views import Homepage, ActivityFeed

urlpatterns = [
    path("", Homepage.as_view(), name="homepage"),
    path("activity-feed", ActivityFeed.as_view(), name="activity_feed"),
]
