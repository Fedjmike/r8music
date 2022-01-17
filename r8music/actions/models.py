from itertools import groupby

from django.db import models
from django.utils import timezone
from django.core.paginator import Paginator

from django.contrib.auth.models import User

from r8music.utils import fuzzy_groupby
from r8music.music.models import Release, Track

class Action(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    creation = models.DateTimeField(default=timezone.now)
    
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

def enact(action):
    """Enact the complete semantics of an action."""

    if isinstance(action, RateAction):
        listen, _ = ListenAction.objects.get_or_create(release=action.release, user=action.user)
        enact(listen)
    
    elif isinstance(action, ListenAction):
        if action.user.settings.listen_implies_unsave:
            action.release_actions(action.release, save_action=None)
        
    action.set_as_active()
    
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

    def action_names(self):
        return list(filter(lambda x: x, (
            self.save_action and "save",
            self.listen and "listen",
            self.rate and "rate"
        )))

#

#The maximum period of time between two actions which can be grouped in an activity feed
max_activity_gap = 4*60*60 #4h in seconds

class ReleaseActivityItem:
    """Represents actions by one user on one release"""
    
    def __init__(self, release, primary_action=None, picks=[]):
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
    """Group a chronological series of actions first by user and creation
       timestamp, then by release."""
    
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

def get_paginated_activity_feed(
    filter_release_actions, filter_track_actions,
    paginate_by, page_no=0
):
    """Get the actions which are active and match a filter, in reverse
       chronological order, grouped by user, creation and release."""
    
    #Separate querysets are needed because the active_actions field involves
    #a different join for each model
    querysets = [
        filter_release_actions(model.objects).exclude(active_actions=None)
        for model in [SaveAction, ListenAction, RateAction]
    ] + [
        filter_track_actions(PickAction.objects).exclude(active_actions=None)
    ]
    
    #The querysets must select a common subset of fields in order to be combined
    querysets = [qs.values_list("id", "creation") for qs in querysets]
    #A queryset of actions of any kind which match the query
    combined_queryset = querysets[0].union(*querysets[1:])
    
    chronological_actions = combined_queryset.order_by("-creation")
    page_of_actions = Paginator(chronological_actions, paginate_by).get_page(page_no)
    
    action_ids = [id for id, creation in page_of_actions]
    
    #To fetch the full objects
    fetch = lambda model, track_action=False: model.objects \
        .select_related("user__profile", "track__release" if track_action else "release") \
        .prefetch_related("track__release__artists" if track_action else "release__artists") \
        .in_bulk(action_ids, field_name="action_ptr_id")
    
    actions_by_id = {
        **fetch(SaveAction), **fetch(ListenAction),
        **fetch(RateAction), **fetch(PickAction, track_action=True)
    }
    
    #Put them back in order
    recent_actions = [actions_by_id[id] for id in action_ids]
    
    #(Return the page object as well)
    return group_actions(recent_actions), page_of_actions
