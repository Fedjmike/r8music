from django.db import models

from r8music.music.models import Artist, Release, DiscogsTag

class ArtistMBLink(models.Model):
    artist = models.OneToOneField(Artist, on_delete=models.CASCADE, related_name="mb_link")
    mbid = models.TextField(unique=True)

class ArtistMBImportation(models.Model):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="mb_importations")
    date = models.DateTimeField(auto_now_add=True)


class ReleaseMBLink(models.Model):
    release = models.OneToOneField(Release, on_delete=models.CASCADE, related_name="mb_link")
    release_mbid = models.TextField(unique=True)
    release_group_mbid = models.TextField(unique=True)
    
class ReleaseDuplication(models.Model):
    """In some cases, an updated release cannot replace the original version."""
    original = models.OneToOneField(Release, on_delete=models.CASCADE, related_name="duplication_of")
    updated = models.ForeignKey(Release, on_delete=models.CASCADE, related_name="duplications")


class ModelMap:
    map_model = None
    from_field = None
    to_field = None
    
    def __init__(self):
        self.update()
        
    def update(self):
        self.id_map = {
            link[self.from_field]: link[self.to_field]
            for link in self.map_model.objects.values(self.from_field, self.to_field)
        }
        
    def get(self, id):
        try:
            return self.id_map[id]
            
        except KeyError as e:
            raise ValueError(f"id={id} was not found") from e
            
    def __contains__(self, id):
        return id in self.id_map

class ArtistMBIDMap(ModelMap):
    map_model = ArtistMBLink
    from_field = "mbid"
    to_field = "artist_id"

class ReleaseMBIDMap(ModelMap):
    map_model = ReleaseMBLink
    from_field = "release_mbid"
    to_field = "release_id"

class DiscogsTagMap(ModelMap):
    map_model = DiscogsTag
    from_field = "discogs_name"
    to_field = "id"
