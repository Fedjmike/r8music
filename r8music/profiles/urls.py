from django.conf.urls import url
from django.urls import path, reverse

from .views import UserMainPage, UserStatsPage

null_view = lambda: None

urlpatterns = [
    path("users", null_view, name="user_index"),
    
    path("user/<slug>", UserMainPage.as_view(), name="user_main"),
    path("user/<slug>/listened-unrated", null_view, name="user_listened_unrated"),
    path("user/<slug>/saved", null_view, name="user_saved"),
    path("user/<slug>/activity", null_view, name="user_activity"),
    path("user/<slug>/friends", null_view, name="user_friends"),
    path("user/<slug>/stats", UserStatsPage.as_view(), name="user_stats"),
    
    path("register", null_view, name="register"),
    path("login", null_view, name="login"),
    path("logout", null_view, name="logout"),
    path("set-password", null_view, name="set-password"),
    path("settings", null_view, name="settings"),
]

def url_for_user(user, route="user_main"):
    return reverse(route, args=[user.username])
    
urlreversers = [url_for_user]
