from django.contrib import admin
from .models import UserSettings, UserProfile, UserRatingDescription, Followership

admin.register([UserSettings, UserProfile, UserRatingDescription, Followership])
