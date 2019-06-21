from django.db import models
from django.contrib.auth.models import User

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
    
    def follows(self, other_user):
        return Followership.objects.filter(user=other_user, follower=self.user).exists()
        
    def friendships(self):
        followers = [f.follower for f in self.user.followers.select_related("follower")]
        following = [f.user for f in self.user.following.select_related("user")]
        
        friends = set(followers + following)
        
        for friend in friends:
            friend.follows = friend in following
            friend.followed_by = friend in followers
            
        return list(friends)
        
class UserRatingDescription(models.Model):
    """The description of this rating displayed on the user's profile page"""
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="rating_descriptions")
    rating = models.IntegerField()
    description = models.TextField()
    
class Followership(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="followers")
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name="following")
    creation = models.DateTimeField(auto_now_add=True)
