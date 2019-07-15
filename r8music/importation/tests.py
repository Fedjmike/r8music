import os, pickle, musicbrainzngs, wikipedia
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


class DiscogsTest(TestCase):
    def setUp(self):
        self.importer = Importer()
        
    def test_discogs_tags(self):
        def json(discogs_url):
            return {
                "url-relation-list": [
                    {"type": "discogs", "target": discogs_url}
                ]
            }
            
        def query(discogs_url, discogs_master_url):
            return self.importer.query_discogs(json(discogs_url), json(discogs_master_url))
            
        def check(results, expected_release_id, expected_master_id, expected_tags):
            release_id, master_id, tags = results
            self.assertEquals(release_id, expected_release_id)
            self.assertEquals(master_id, expected_master_id)
            self.assertEquals(set(tags), set(expected_tags))
            
        #No discogs link
        check(self.importer.query_discogs({}, {}), None, None, [])
        
        #A release with some tags, including one to be excluded.
        check(
            query("https://www.discogs.com/release/4577604", "https://www.discogs.com/master/4030"),
            "4577604", "4030", ["Blues", "Folk"]
        )


class CoverArtTest(TestCase):
    def setUp(self):
        self.mb_fixture = fixture_path("cover_art_test")
        
        self.memoized_musicbrainz = MemoizedModule(
            musicbrainzngs, exceptions=["set_useragent"], mock_only=True,
            storage=try_load_memoization(self.mb_fixture)
        )
        
        self.importer = Importer(musicbrainz=self.memoized_musicbrainz)
        
    def save_fixtures(self):
        save_memoization(self.memoized_musicbrainz.storage, self.mb_fixture)
        
    def test_cover_art(self):
        def json(mbid, has_artwork):
            return {
                "id": mbid,
                "cover-art-archive": {"artwork": "true" if has_artwork else "false"}
            }
            
        def query(release_mbid, release_group_mbid, release_artwork=True, release_group_artwork=True):
            return self.importer.query_cover_art(
                json(release_mbid, release_artwork),
                json(release_group_mbid, release_group_artwork)
            )
            
        def check(art_urls):
            self.assertEquals(set(art_urls.keys()), set(["max", "250", "500"]))
            
            for url in art_urls.values():
                self.assertIsNotNone(url)
        
        #Art for group but not release. A query whose response from the CAA uses
        #the old keys, "large" and "small", not "500" and "250".
        check(query(
            "672de9bc-fca5-4d26-84fd-075ab440c753", "06448e12-18d8-4d52-a51f-d4c83d07ec09",
            release_artwork=False
        ))
        
        #Art for both release and group. The response uses the new keys.
        check(query("508a9f90-bf4b-46ee-a5d4-5d09c40ea6d5", "696f2388-f520-4e50-bcc6-9c58dcfd879c"))
        
        #No cover art
        self.assertIsNone(query(
            "ba45590f-8e3b-48aa-9082-f2f7f22460ac", "5c9f1f0f-d079-4fa3-b2b7-858249c36703",
            release_artwork=False, release_group_artwork=False
        ))
