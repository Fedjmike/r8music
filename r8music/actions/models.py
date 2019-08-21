from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from django.contrib.auth.models import User
from r8music.music.models import Release, Track

class Action(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    creation = models.DateTimeField(auto_now_add=True)
    
    def release_actions(self, release, **changes):
        return release.active_actions.update_or_create(user=self.user, defaults=changes)[0]
        
class SaveAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    
    def set_as_active(self):
        self.release_actions(self.release, save_action=self)
    
class ListenAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    
    def set_as_active(self):
        self.release_actions(self.release, listen=self)
    
class RateAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    rating = models.IntegerField()
    
    def set_as_active(self):
        self.release_actions(self.release, rate=self)
    
class PickAction(Action):
    track = models.ForeignKey(Track, on_delete=models.PROTECT, related_name="pick_actions")
    
    def set_as_active(self):
        self.release_actions(self.track.release).picks.add(self)

@receiver(post_save, sender=SaveAction)
@receiver(post_save, sender=ListenAction)
@receiver(post_save, sender=RateAction)
@receiver(post_save, sender=PickAction)
def action_post_save(sender, instance, created, **kwargs):
    if created:
        instance.set_as_active()

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
