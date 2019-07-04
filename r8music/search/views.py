from urllib.parse import urlencode

from django.views.generic import View, TemplateView
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.urls import reverse

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

from r8music.music.models import Release, Artist

class Search:
    #The minimum search rank to be included
    #Some irrelevant results still get above zero (e.g. 1e-20).
    rank_threshold = 0.001

    def __init__(self, query_str):
        #:* allows prefix matches, quotes escape the query from the search syntax
        self.query = SearchQuery("'%s':*" % query_str, search_type="raw")
        
    def search(self, model, search_vector):
        return model.objects \
            .annotate(rank=SearchRank(search_vector, self.query)) \
            .filter(rank__gte=self.rank_threshold) \
            .order_by("-rank")
        
    def search_artists(self):
        return self.search(Artist, SearchVector("name"))
        
    def search_releases(self):
        return self.search(Release, SearchVector("title"))
        
def encode_query_str(query):
    #Not a bijection: ' ' and '+' both go to '+'
    return "+".join(query.split(" "))
    
def decode_query_str(query):
    return query.replace("+", " ")

class SearchPage(View):
    http_method_names = ["get", "post"]
    
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
            return render(request, "search_form.html")
            
    def post(self, request):
        #Redirect to an URL with the query from the submitted form as a parameter
        query = request.POST.get("query")
        url_as_get = reverse("search", ) + "?" + urlencode({"q": query})
        return redirect(url_as_get)
