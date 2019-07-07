from urllib.parse import urlencode
from django.urls import reverse

from django.views.generic import View, ListView
from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response

from django.db.models import Value, IntegerField
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

from r8music.music.models import Release, Artist
from r8music.music.urls import url_for_artist, url_for_release

class AbstractSearchPage:
    #The minimum search rank to be included
    #Some irrelevant results still get above zero (e.g. 1e-20).
    rank_threshold = 0.001
    
    def get_query_str(self):
        query_param = self.request.GET.get("q")
        #Translate the query as it appeared in the URL into what the user typed
        return query_param.replace("+", " ")
        
    def get_search_url(self, view_name):
        query_param = self.request.GET.get("q")
        return reverse(view_name) + "?" + urlencode({"q": query_param})
        
    def search(self, model, search_vector, order):
        query_str = self.get_query_str()
        #:* allows prefix matches, quotes escape the query from the search syntax
        query = SearchQuery("'%s':*" % query_str, search_type="raw")
        
        return model.objects \
            .annotate(rank=SearchRank(search_vector, query)) \
            .filter(rank__gte=self.rank_threshold) \
            .order_by("-rank", order)
        
    def search_artists(self):
        return self.search(Artist, SearchVector("name"), order="name")
        
    def search_releases(self):
        return self.search(Release, SearchVector("title"), order="release_date")

class GeneralSearchPage(View, AbstractSearchPage):
    def get_results_page(self):
        return render(self.request, "search/general_results.html", {
            "query": self.get_query_str(),
            "artists": self.search_artists()[:10],
            "releases": self.search_releases().prefetch_related("artists")[:10],
            "url_for_artist_search": self.get_search_url("artist_search"),
            "url_for_release_search": self.get_search_url("release_search")
        })
        
    def get(self, request):
        if request.GET.get("q"):
            return self.get_results_page()
            
        else:
            return render(request, "search/search_form.html")

class AbstractCategorySearchPage(ListView, AbstractSearchPage):
    context_object_name = "results"
    
    def get_context_data(self):        
        return super().get_context_data(
            query=self.get_query_str(),
            url_for_general_search=self.get_search_url("search")
        )
        
class ArtistSearchPage(AbstractCategorySearchPage):
    template_name = "search/artist_results.html"
    paginate_by = 25
    
    def get_queryset(self):
        return self.search_artists()
    
class ReleaseSearchPage(AbstractCategorySearchPage):
    template_name = "search/release_results.html"
    paginate_by = 18
    
    def get_queryset(self):
        return self.search_releases().prefetch_related("artists")

class SearchAPI(APIView, AbstractSearchPage):
    """"An API for search autocompletion"""
    
    def get(self, request):
        #Used to differentiate search result kinds
        artist_category, release_category = 0, 1
        
        #Combine search results from different categories (by only selecting the same columns)
        artist_qs = self.search_artists() \
            .values("id", "rank", category=Value(artist_category, IntegerField()))
        release_qs = self.search_releases() \
            .values("id", "rank", category=Value(release_category, IntegerField()))
        results = artist_qs.union(release_qs)
        
        results = results.order_by("-rank")[:15]
        
        artist_ids, release_ids = (
            (r["id"] for r in results if r["category"] == category)
            for category in [artist_category, release_category]
        )
        
        #Fetch the full objects and turn them into menu items
        
        artists = [
            {"name": artist.name, "url": url_for_artist(artist)}
            for artist in Artist.objects.in_bulk(artist_ids).values()
        ]
        
        releases = [
            {
                "name": release.title + " by "
                    + " & ".join(artist.name for artist in release.artists.all()),
                "url": url_for_release(release)
            }
            for release in Release.objects.in_bulk(release_ids).values()
        ]
        
        return Response({
            #Show artists before releases (for predictability as much as code simplicity)
            "results": artists + releases
        })