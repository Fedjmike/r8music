import requests
from itertools import groupby
from collections import Counter
from urllib.parse import urlparse

from django.views.generic import TemplateView, DetailView, ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView, PasswordChangeDoneView, redirect_to_login
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils.html import escape

from rest_framework.decorators import api_view
from rest_framework.response import Response

from django import forms
from django.contrib.auth.forms import UserCreationForm
from captcha.fields import ReCaptchaField

from django.db.models import Count, Q

from django.contrib.auth.models import User
from r8music.profiles.models import UserSettings, UserProfile, UserRatingDescription
from r8music.music.models import Release
from r8music.actions.models import get_paginated_activity_feed

from django.urls import reverse_lazy

class UserIndex(ListView):
    model = User
    template_name = "user_index.html"
    paginate_by = 25
    
    def get_queryset(self):
        return User.objects.order_by("id")

#

class AbstractUserPage(DetailView):
    model = User
    
    def get_object(self):
        return get_object_or_404(User, username=self.kwargs.get("slug"))
        
    def get_actions_counts(self, user):
        """Return the number of releases interacted with in certain ways by a user."""
        return user.active_actions.aggregate(
            rated=Count("id", filter=~Q(rate=None)),
            listened_unrated=Count("id", filter=~Q(listen=None) & Q(rate=None)),
            saved=Count("id", filter=~Q(save_action=None))
        )
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_counts"] = self.get_actions_counts(context["user"])
        return context
        
class UserMainPage(AbstractUserPage):
    template_name = "user_main.html"
    
    def add_releases_rated_data(self, context):
        #The user whose profile is being viewed
        user = context["user"]
        
        releases_rated = Release.objects \
            .rated_by_user(user) \
            .order_by("-rating_by_user", "artists__name", "release_date") \
            .prefetch_related("artists")
        
        descriptions = {desc.rating: desc.description for desc in user.profile.rating_descriptions.all()}
        
        #The releases rated by the user, grouped by rating, as list of tuples,
        #[(rating, rating_description, [releases])], where rating_description is the
        #heading given by the user for that rating group."""
        context["releases_rated_groups"] = [
            (rating, descriptions.get(rating, None), list(releases))
            for rating, releases in groupby(releases_rated, lambda r: r.rating_by_user)
        ]
        
        rated_by_request_user = Release.objects \
            .rated_by_user(self.request.user) \
            .in_bulk([r.id for r in releases_rated]) \
            if not self.request.user.is_anonymous else {}
        
        context["get_user_rating"] = lambda release: rated_by_request_user[release.id].rating_by_user \
            if release.id in rated_by_request_user else None
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        self.add_releases_rated_data(context)
        return context

class UserListenedUnratedPage(AbstractUserPage):
    template_name = "user_listened_unrated.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["listened_unrated"] = Release.objects.listened_unrated_by_user(context["user"]).prefetch_related("artists")
        return context

class UserSavedPage(AbstractUserPage):
    template_name = "user_saved.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["saved"] = Release.objects.saved_by_user(context["user"])
        return context

class UserActivityPage(AbstractUserPage):
    template_name = "user_activity.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        user = context["user"]
        page_no = self.request.GET.get("page")
        
        context["activity"], context["page_obj"] = get_paginated_activity_feed(
            lambda release_actions: release_actions.filter(user=user),
            #Exclude actions on tracks
            lambda track_actions: track_actions.filter(pk=None),
            paginate_by=20, page_no=page_no
        )
        
        return context

class UserFriendsPage(AbstractUserPage):
    template_name = "user_friends.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["friends"] = context["user"].profile.friendships()
        return context

class UserStatsPage(AbstractUserPage):
    template_name = "user_stats.html"
    
    def get_rating_counts(self, user):
        """Return counts of releases given each rating by a user."""
        
        rating_counts = user.active_actions.aggregate(**{
            ("rated_%d" % n): Count("id", filter=Q(rate__rating=n))
            for n in range(1, 8+1)
        })
        
        return [rating_counts["rated_%d" % n] for n in range(1, 8+1)]
        
        
    def get_release_year_counts(self, user):
        """Return counts of releases listened to by a user for each year between
           the years of the earliest and latest releases, as ([years], [counts])."""
        
        release_dates = user.active_actions \
            .exclude(listen=None) \
            .order_by("release__release_date") \
            .values_list("release__release_date", flat=True)
        release_years = [int(date[:4]) for date in release_dates if date]
        
        year_counts = Counter(release_years)
        
        range_of = lambda iterable: \
            range(min(iterable), max(iterable)+1) if iterable else []
        year_range = list(range_of(list(year_counts.keys())))
        
        return (year_range, [year_counts.get(year, 0) for year in year_range])
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["rating_counts"] = self.get_rating_counts(context["user"])
        context["release_year_counts"] = self.get_release_year_counts(context["user"])
        return context

# User 'post' views which redirect to the referrer

class FollowUser(AbstractUserPage, LoginRequiredMixin):
    model = User
    http_method_names = ["post"]
    
    def post(self, request, **kwargs):
        request.user.following.get_or_create(user=self.get_object())
        return redirect(request.POST.get("next"))

class UnfollowUser(AbstractUserPage, LoginRequiredMixin):
    model = User
    http_method_names = ["post"]
    
    def post(self, request, **kwargs):
        request.user.following.filter(user=self.get_object()).delete()
        return redirect(request.POST.get("next"))

#

class R8MUserCreationForm(UserCreationForm):
    #Require Google recaptcha confirmation (by default, the checkbox)
    captcha = ReCaptchaField()

class RegistrationPage(CreateView):
    template_name = "registration/register.html"
    form_class = R8MUserCreationForm
    success_url = reverse_lazy("login")
    
    def form_valid(self, form):
        redirect_without_next = super().form_valid(form)
        
        if "next" in self.request.POST:
            return redirect_to_login(self.request.POST.get("next"), login_url=self.success_url)
            
        else:
            return redirect_without_next

class ChangePasswordPage(PasswordChangeView):
    template_name = "registration/change_password.html"
    success_url = reverse_lazy("password_change_done")
    
class PasswordChangeDonePage(PasswordChangeDoneView):
    template_name = "registration/password_change_done.html"

# Settings

class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("email",)
        
class SettingsForm(forms.ModelForm):
    class Meta:
        model = UserSettings
        fields = ("timezone", "listen_implies_unsave")
        labels = {"listen_implies_unsave": "Listening to a release unsaves it"}
        
class ProfileForm(forms.ModelForm):
    approved_hosts = ["i.imgur.com", "my.mixtape.moe"]
    max_file_size = 500*1024 # 500 kB
    allowed_exts = ["jpg", "jpeg", "png"]
    
    class Meta:
        model = UserProfile
        fields = ("avatar_url",)
        labels = {"avatar_url": "Avatar URL"}
        
    def clean_avatar_url(self):
        avatar_url = self.cleaned_data["avatar_url"]
        _, domain, path, _, _, _ = urlparse(avatar_url)
        
        if domain not in self.approved_hosts:
            raise forms.ValidationError(
                 "'%s' is not a whitelisted host. Approved hosts: %s"
                 % (domain, ", ".join(self.approved_hosts))
            )
        
        elif path.split(".")[-1] not in self.allowed_exts:
            raise forms.ValidationError("Must be a JPG or PNG image")
            
        try:
            response = requests.head(avatar_url)
            file_size = int(response.headers.get("content-length", 0))
            
            if not response:
                raise ValueError()
            
        except (requests.exceptions.RequestException, ValueError):
            raise forms.ValidationError("Invalid URL")
        
        else:
            if file_size > self.max_file_size:
                raise forms.ValidationError(
                    "File size (%s kB) exceeds the maximum (%s kB)"
                    % (file_size // 1024, self.max_file_size // 1024)
                )
            
        return avatar_url

class SettingsPage(LoginRequiredMixin, TemplateView):
    template_name = "registration/settings.html"
    
    def get_forms(self):
        kwargs = {} if self.request.method != "POST" else {
            "data": self.request.POST,
            "files": self.request.FILES,
        }
        
        return (
            UserForm(instance=self.request.user, **kwargs),
            SettingsForm(instance=self.request.user.settings, **kwargs),
            ProfileForm(instance=self.request.user.profile, **kwargs)
        )
        
    def get_context_data(self, **kwargs):
        user_form, settings_form, profile_form = self.get_forms()
        return super().get_context_data(
            user_form=user_form, settings_form=settings_form, profile_form=profile_form)
        
    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data())
        
    def post(self, request, *args, **kwargs):
        errors = False
        
        for form in self.get_forms():
            try:
                form.save()
                
            except ValueError:
                errors = True
                
        if not errors:
            messages.success(request, "Settings saved")
        
        return self.render_to_response(self.get_context_data())

# User API

@api_view(["post"])
@login_required
def rating_description(request):
    try:
        rating = int(request.data.get("rating"))
        description = escape(request.data.get("description"))

    except ValueError:
        return Response(
            {"error": "Rating not provided, or not an integer"},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    if not description:
        return Response(
            {"error": "Description not provided"},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    else:
        rd, _ = UserRatingDescription.objects.get_or_create(
            user=request.user.profile, rating=rating)
        rd.description = description
        rd.save()
        
        return Response()
