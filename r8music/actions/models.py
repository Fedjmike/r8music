from django.db import models

from django.contrib.auth.models import User
from r8music.music.models import Release, Track

class Action(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    creation = models.DateTimeField(auto_now_add=True)
    
    def _get_active_actions(self, object):
        return object.active_actions.get_or_create(user=self.user)[0]
        
class SaveAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    
    def set_as_active(self):
        active_actions = self._get_active_actions(self.release)
        active_actions.save_action = self
        active_actions.save()
    
class ListenAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    
    def set_as_active(self):
        active_actions = self._get_active_actions(self.release)
        active_actions.listen = self
        active_actions.save()
    
class RateAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    rating = models.IntegerField()
    
    def set_as_active(self):
        active_actions = self._get_active_actions(self.release)
        active_actions.rate = self
        active_actions.save()
    
class PickAction(Action):
    track = models.ForeignKey(Track, on_delete=models.PROTECT)
    
    def set_as_active(self):
        active_actions = self._get_active_actions(self.track.release)
        active_actions.picks.add(self)

#

class ActiveActions(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="active_actions")
    release = models.ForeignKey(Release, on_delete=models.PROTECT, related_name="active_actions")
    
    #The existence of an action only means that action was taken at some point.
    #If the user undoes that action, it is removed from these fields.
    save_action = models.ForeignKey(SaveAction, on_delete=models.PROTECT, null=True)
    listen = models.ForeignKey(ListenAction, on_delete=models.PROTECT, null=True)
    rate = models.ForeignKey(RateAction, on_delete=models.PROTECT, null=True)
    picks = models.ManyToManyField(PickAction)
    
    def picked_tracks(self):
        return self.picks.all().values_list("track_id", flat=True)
        
    def rating(self):
        return self.rate.rating if self.rate else None
