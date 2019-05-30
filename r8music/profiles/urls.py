from django.conf.urls import url
from django.urls import path, reverse

null_view = lambda: None

urlpatterns = [
    path("users", null_view, name="user_index"),
    path("user/<slug>", null_view, name="user"),
    path("register", null_view, name="register"),
    path("login", null_view, name="login"),
    path("logout", null_view, name="logout"),
    path("set-password", null_view, name="set-password"),
    path("settings", null_view, name="settings"),
]
