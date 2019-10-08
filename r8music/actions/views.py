from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from rest_framework import views, permissions, renderers
from rest_framework.response import Response

from django.db.models import Q
from r8music.actions.models import get_paginated_activity_feed

def get_user_activity_feed(user, page_no=1, paginate_by=25):
    return get_paginated_activity_feed(
        lambda release_actions: release_actions
            .filter(Q(user__followers__follower=user) | Q(user=user)),
        #Exclude actions on tracks
        lambda track_actions: track_actions.filter(pk=None),
        paginate_by=paginate_by, page_no=page_no
    )

class Homepage(LoginRequiredMixin, TemplateView):
    template_name = "homepage.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["activity"], context["page_obj"] = \
            get_user_activity_feed(self.request.user)
        return context

class ActivityFeed(views.APIView):
    permission_classes = (permissions.IsAuthenticated,)
    renderer_classes = [renderers.TemplateHTMLRenderer]
    
    def get(self, request):
        page_no = request.query_params.get("page_no")
        activity, page_obj = get_user_activity_feed(self.request.user, page_no)
        return Response({"activity": activity}, template_name="activity_feed.html")
