from django.db import models
from django.contrib.auth.models import User

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    #Stored as a UTC offset, in the format "[+-]\d\d:\d\d"
    timezone = models.TextField()
    #Does 'listening' to a release automatically remove it from the 'saved' list?
    listen_implies_unsave = models.BooleanField()

#

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    avatar_url = models.TextField()
    
class UserRatingDescription(models.Model):
    """The description of this rating displayed on the user's profile page"""
    user = models.ForeignKey(UserProfile, on_delete=models.PROTECT, related_name="rating_descriptions")
    rating = models.IntegerField()
    description = models.TextField()
    
class Followership(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.PROTECT, related_name="followers")
    follower = models.ForeignKey(UserProfile, on_delete=models.PROTECT, related_name="following")
    creation = models.DateTimeField(auto_now_add=True)
