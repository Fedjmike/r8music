from urllib.parse import urlencode

from django.views.generic import View, TemplateView
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.urls import reverse

from django.contrib.postgres.search import SearchQuery

from r8music.music.models import Release, Artist

def search(query_str):
    #:* allows prefix matches, quotes escape the query from the search syntax
    query = SearchQuery("'%s':*" % query_str, search_type="raw")
    return Artist.objects.filter(name__search=query)

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
        page = request.GET.get("page")
        
        query = decode_query_str(query_str)
        full_results = search(query)
        results = Paginator(full_results, self.paginate_by).get_page(page)
        
        context = {
            "query": query,
            "results": results
        }
        
        return render(request, "search_results.html", context)
        
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
