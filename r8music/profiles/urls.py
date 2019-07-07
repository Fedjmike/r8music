from django.conf.urls import url, include
from django.urls import path, reverse

from .views import UserIndex, UserMainPage, UserListenedUnratedPage, UserSavedPage, UserFriendsPage, UserStatsPage
from .views import FollowUser, UnfollowUser, rating_description

null_view = lambda: None

urlpatterns = [
    path("users", UserIndex.as_view(), name="user_index"),
    
    path("user/<slug>", UserMainPage.as_view(), name="user_main"),
    path("user/<slug>/listened-unrated", UserListenedUnratedPage.as_view(), name="user_listened_unrated"),
    path("user/<slug>/saved", UserSavedPage.as_view(), name="user_saved"),
    path("user/<slug>/activity", null_view, name="user_activity"),
    path("user/<slug>/friends", UserFriendsPage.as_view(), name="user_friends"),
    path("user/<slug>/stats", UserStatsPage.as_view(), name="user_stats"),
    
    path("user/<slug>/follow", FollowUser.as_view(), name="follow_user"),
    path("user/<slug>/unfollow", UnfollowUser.as_view(), name="unfollow_user"),
    
    path("settings/rating-description", rating_description, name="rating_description"),

    path("accounts/", include("django.contrib.auth.urls")),
    path("register", null_view, name="register"),
    path("settings", null_view, name="settings"),
]

def url_for_user(user, route="user_main"):
    return reverse(route, args=[user.username])
    
urlreversers = [url_for_user]
