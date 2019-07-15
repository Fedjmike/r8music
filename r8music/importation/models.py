from django.db import models

from r8music.music.models import Artist, Release

class ArtistMBLink(models.Model):
    artist = models.OneToOneField(Artist, on_delete=models.CASCADE, related_name="mb_link")
    mbid = models.TextField()

class ArtistMBImportation(models.Model):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="mb_importations")
    date = models.DateTimeField(auto_now_add=True)


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

class ArtistMBIDMap(ModelMap):
    map_model = ArtistMBLink
    from_field = "mbid"
    to_field = "artist_id"
