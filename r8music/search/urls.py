from django.conf.urls import url
from django.urls import path

from .views import SearchPage

urlpatterns = [
    path("search", SearchPage.as_view(), name="search"),
]
