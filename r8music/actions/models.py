from django.db import models

from r8music.music.models import Release, Track
from r8music.profiles.models import UserProfile

class Action(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.PROTECT)
    creation = models.DateTimeField(auto_now_add=True)
    
class ReleaseAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)

class SaveAction(ReleaseAction):
    pass
    
class ListenAction(ReleaseAction):
    pass
    
class RatingAction(ReleaseAction):
    rating = models.IntegerField()
    
class PickAction(Action):
    track = models.ForeignKey(Track, on_delete=models.PROTECT)
    
class LatestActions(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.PROTECT)
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    
    saved = models.ForeignKey(SaveAction, on_delete=models.PROTECT, null=True)
    listened = models.ForeignKey(ListenAction, on_delete=models.PROTECT, null=True)
    rating = models.ForeignKey(RatingAction, on_delete=models.PROTECT, null=True)
    picks = models.ManyToManyField(PickAction)
