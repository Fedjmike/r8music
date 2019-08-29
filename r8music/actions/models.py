from itertools import groupby
from r8music.utils import fuzzy_groupby

from django.db import models
from model_utils.managers import InheritanceManager
from django.utils import timezone

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from django.contrib.auth.models import User
from r8music.music.models import Release, Track

class Action(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    creation = models.DateTimeField(default=timezone.now)
    
    objects = InheritanceManager()
    
    def release_actions(self, release, **changes):
        return release.active_actions.update_or_create(user=self.user, defaults=changes)[0]
        
class SaveAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    
    def describe(self):
        return "saved"
        
    def set_as_active(self):
        self.release_actions(self.release, save_action=self)
    
class ListenAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    
    def describe(self):
        return "listened"
        
    def set_as_active(self):
        self.release_actions(self.release, listen=self)
    
class RateAction(Action):
    release = models.ForeignKey(Release, on_delete=models.PROTECT)
    rating = models.IntegerField()
    
    def describe(self):
        return "rated %d" % self.rating
        
    def set_as_active(self):
        self.release_actions(self.release, rate=self)
    
class PickAction(Action):
    track = models.ForeignKey(Track, on_delete=models.PROTECT, related_name="pick_actions")
    
    @property
    def release(self):
        return self.track.release
    
    def set_as_active(self):
        self.release_actions(self.track.release).picks.add(self)

@receiver(pre_save, sender=ListenAction)
def listen_pre_save(sender, instance, **kwargs):
    if instance.user.settings.listen_implies_unsave:
        instance.release_actions(instance.release, save_action=None)
    
@receiver(pre_save, sender=RateAction)
def rate_pre_save(sender, instance, **kwargs):
    ListenAction.objects.create(release=instance.release, user=instance.user)

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
    save_action = models.ForeignKey(SaveAction, on_delete=models.PROTECT, null=True, related_name="active_actions")
    listen = models.ForeignKey(ListenAction, on_delete=models.PROTECT, null=True, related_name="active_actions")
    rate = models.ForeignKey(RateAction, on_delete=models.PROTECT, null=True, related_name="active_actions")
    picks = models.ManyToManyField(PickAction, related_name="active_actions")
    
    def picked_tracks(self):
        return self.picks.all().values_list("track_id", flat=True)
        
    def rating(self):
        return self.rate.rating if self.rate else None

#

#The maximum gap between two actions which can be grouped in an activity feed
max_activity_gap = 4*60*60 #4h in seconds

class ReleaseActivityItem:
    """Represents actions by one user on one release"""
    
    def __init__(self, release, primary_action, picks):
        self.release = release
        #The most interesting action, the one worth mentioning
        self.primary_action = primary_action
        self.picks = picks
        
    @staticmethod
    def from_actions(release, actions):
        primary_action = next(filter(lambda x: x, [
            next((action for action in actions if isinstance(action, model)), None)
            #Prioritise the kinds of release actions in this order
            for model in [RateAction, ListenAction, SaveAction]
        ]), None)
        
        picks = filter(lambda action: isinstance(action, PickAction), actions)
        
        return ReleaseActivityItem(release, primary_action, picks)
        
class UserActivityGroup:
    """Represents actions by one user"""
    
    def __init__(self, user, activity):
        self.user = user
        self.activity = activity
        
def group_actions(actions):
    """Group a chronological series of actions by user, creation and release."""
    
    return [
        UserActivityGroup(user, [
            ReleaseActivityItem.from_actions(release, list(actions_on_release))
            for release, actions_on_release in groupby(close_actions, key=lambda action: action.release)
        ])
        for user, actions_by_user in groupby(actions, key=lambda action: action.user)
        for timestamp, close_actions in fuzzy_groupby(
            actions_by_user, threshold=max_activity_gap,
            key=lambda action: action.creation.timestamp()
        )
    ]

def get_activity_feed(filter_release_actions, filter_track_actions):
    """Get the actions which are active and match a filter, in reverse
       chronological order, grouped by user, creation and release."""
    
    querysets = [
        filter_release_actions(model.objects).exclude(active_actions=None)
        for model in [SaveAction, ListenAction, RateAction]
    ] + [
        filter_track_actions(PickAction.objects).exclude(active_actions=None)
    ]

    #The querysets must select the same values in order to be combined
    querysets = [qs.values_list("id", "creation") for qs in querysets]
    #A queryset of actions of any kind which match the query
    combined_queryset = querysets[0].union(*querysets[1:])
    
    recent_actions = combined_queryset.order_by("-creation")
    recent_action_ids = [id for id, creation in recent_actions]
    
    #Fetch the full objects and put them in order
    actions_by_id = Action.objects.select_subclasses().in_bulk(recent_action_ids)
    recent_actions = [actions_by_id[id] for id in recent_action_ids]
    
    return group_actions(recent_actions)
