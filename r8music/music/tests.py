from django.test import TestCase
from django.core.exceptions import ValidationError

from .models import Artist, generate_slug

class SlugTest(TestCase):
    #Fields which won't be assigned valid values
    other_fields = ["description", "image_url", "image_thumb_url"]
    
    def test(self):
        is_free = lambda slug: True
        
        def create_artist_and_clean(name):
            try:
                Artist.objects \
                    .create(name=name, slug=generate_slug(is_free, name)) \
                    .clean_fields(exclude=self.other_fields)
            
            except ValidationError:
                self.fail("ValidationError raised when name=" + repr(name))
            
        create_artist_and_clean("+-")
        create_artist_and_clean("シートベルツ")
