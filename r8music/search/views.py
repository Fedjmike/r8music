from django.views.generic import View, TemplateView
from django.shortcuts import render
from django.core.paginator import Paginator

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

from r8music.music.models import Release, Artist

class Search:
    #The minimum search rank to be included
    #Some irrelevant results still get above zero (e.g. 1e-20).
    rank_threshold = 0.001

    def __init__(self, query_str):
        #:* allows prefix matches, quotes escape the query from the search syntax
        self.query = SearchQuery("'%s':*" % query_str, search_type="raw")
        
    def search(self, model, search_vector, order):
        return model.objects \
            .annotate(rank=SearchRank(search_vector, self.query)) \
            .filter(rank__gte=self.rank_threshold) \
            .order_by("-rank", order)
        
    def search_artists(self):
        return self.search(Artist, SearchVector("name"), order="name")
        
    def search_releases(self):
        return self.search(Release, SearchVector("title"), order="release_date")
        
def decode_query_str(query):
    return query.replace("+", " ")

class SearchPage(View):
    paginate_by = 25
    
    def get_results_page(self, request):
        query_str = request.GET.get("q")
        category = request.GET.get("category")
        page = request.GET.get("page")
        
        query = decode_query_str(query_str)
        search = Search(query)
        
        if category == "release":
            full_results = search.search_releases()
            template_name = "search/release_results.html"
            
        elif category == "artist":
            full_results = search.search_artists()
            template_name = "search/artist_results.html"    
            
        results = Paginator(full_results, self.paginate_by).get_page(page)
        
        return render(request, template_name, {
            "query": query,
            "results": results
        })
        
    def get(self, request):
        if request.GET.get("q"):
            return self.get_results_page(request)
            
        else:
            return render(request, "search/search_form.html")
