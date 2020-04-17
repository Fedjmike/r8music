from django.views.generic import TemplateView

from rest_framework import views, renderers
from rest_framework.response import Response

from django.db.models import Q
from r8music.actions.models import get_paginated_activity_feed

def get_user_activity_feed(user, page_no=1, paginate_by=25):
    def filter_release_actions(release_actions):
        #Actions from friends, and the user themself
        return release_actions \
            .filter(Q(user__followers__follower=user) | Q(user=user))
            
    #Show anonymous visitors a universal activity feed
    if user.is_anonymous:
        filter_release_actions = lambda a: a
    
    return get_paginated_activity_feed(
        filter_release_actions,
        #Exclude actions on tracks
        lambda track_actions: track_actions.filter(pk=None),
        paginate_by=paginate_by, page_no=page_no
    )

class Homepage(TemplateView):
    template_name = "homepage.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activity"], context["page_obj"] = \
            get_user_activity_feed(self.request.user)
        return context

class ActivityFeed(views.APIView):
    renderer_classes = [renderers.TemplateHTMLRenderer]
    
    def get(self, request):
        page_no = request.query_params.get("page_no")
        activity, _page_obj = get_user_activity_feed(self.request.user, page_no)
        return Response({"activity": activity}, template_name="activity_feed.html")
