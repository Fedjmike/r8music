from django.db import models
from django.contrib.auth.models import User

from r8music.actions.models import ActiveActions

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")
    #Stored as a UTC offset, in the format "[+-]\d\d:\d\d"
    timezone = models.TextField()
    #Does 'listening' to a release automatically remove it from the 'saved' list?
    listen_implies_unsave = models.BooleanField()

#

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar_url = models.TextField()
    
    def actions_on_release(self, release_id):
        try:
            return self.user.active_actions.get(release_id=release_id)
            
        except ActiveActions.DoesNotExist:
            return None
        
class UserRatingDescription(models.Model):
    """The description of this rating displayed on the user's profile page"""
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="rating_descriptions")
    rating = models.IntegerField()
    description = models.TextField()
    
class Followership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers")
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="following")
    creation = models.DateTimeField(auto_now_add=True)
