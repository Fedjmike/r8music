import os, pickle, wikipedia
from django.test import TestCase

from .utils import MemoizedModule
from .importer import Importer

package_directory = os.path.dirname(os.path.abspath(__file__))

def fixture_path(name):
    return os.path.join(package_directory, "fixtures", name + ".pickle")
    
def try_load_memoization(filename):
    try:
        with open(filename, "rb") as f:
            return pickle.load(f)
            
    except (IOError, TypeError):
        pass
    
def save_memoization(storage, filename):
    with open(filename, "wb") as f:
        pickle.dump(storage, f)


class WikipediaTest(TestCase):
    """Tests wikipedia querying.
       
       It loads a memoized version of the wikipedia API from a fixture, allowing
       the test to be tied to the version of the wikipedia data it was written for."""
    
    def setUp(self):
        self.wikipedia_fixture = fixture_path("wikipedia_test")
        
        self.memoized_wikipedia = MemoizedModule(
            wikipedia, mock_only=True,
            storage=try_load_memoization(self.wikipedia_fixture)
        )
        
        self.importer = Importer(wikipedia=self.memoized_wikipedia)
        
    def save_fixtures(self):
        save_memoization(self.memoized_wikipedia.storage, self.wikipedia_fixture)
    
    def test_wikipedia(self):
        def check(results, expected_guessed_url, description_expected, images_expected):
            guessed_url, description, images = results
            
            if expected_guessed_url:
                self.assertEqual(guessed_url, expected_guessed_url)
            
            else:
                self.assertIsNone(guessed_url)
                
            (self.assertIsNotNone if description_expected else self.assertIsNone)(description)
            (self.assertIsNotNone if images_expected else self.assertIsNone)(images)
            
            if images_expected:
                try:
                    thumb, full_image = images
                    
                except TypeError:
                    self.fail("'images' is not a 2-tuple")
                
                else:
                    map(self.assertIsNotNone, [thumb, full_image])
        
        #Guessed URL
        results = self.importer.query_wikipedia("Julien Baker")
        check(results, "https://en.wikipedia.org/wiki/Julien_Baker", True, True)
        
        #Guessed via a disambiguation page
        results = self.importer.query_wikipedia("Can")
        check(results, "https://en.wikipedia.org/wiki/Can_(band)", True, True)
        
        #No wikipedia page (despite a redirect to /wiki/Dud)
        results = self.importer.query_wikipedia("Duds")
        check(results, None, False, False)
        
        #Provided URL, no image
        results = self.importer.query_wikipedia("Shopping", "https://en.wikipedia.org/wiki/Shopping_(band)")
        check(results, None, True, False)
