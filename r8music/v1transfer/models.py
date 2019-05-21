from django.db import models

from django.contrib.auth.models import User
from r8music.music.models import Artist, Release, Track, Tag
from r8music.actions.models import Action

#These tables link objects with those they were imported from in the V1 database

class UserV1Link(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    old_id = models.IntegerField(unique=True)
    #If this user still uses a password created in V1,
    #the (Flask created) hash is stored here.
    password_hash = models.TextField(null=True)
    
class TagV1Link(models.Model):
    tag = models.OneToOneField(Tag, on_delete=models.CASCADE)
    old_id = models.IntegerField(unique=True)

class ArtistV1Link(models.Model):
    artist = models.OneToOneField(Artist, on_delete=models.CASCADE)
    old_id = models.IntegerField(unique=True)
    
class ReleaseV1Link(models.Model):
    release = models.OneToOneField(Release, on_delete=models.CASCADE)
    old_id = models.IntegerField(unique=True)
    
class TrackV1Link(models.Model):
    track = models.OneToOneField(Track, on_delete=models.CASCADE)
    old_id = models.IntegerField(unique=True)

class ActionV1Link(models.Model):
    action = models.OneToOneField(Action, on_delete=models.CASCADE)
    old_id = models.IntegerField(unique=True)
