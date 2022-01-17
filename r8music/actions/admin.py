from django.contrib import admin
from .models import SaveAction, ListenAction, RateAction, ActiveActions

admin.site.register([SaveAction, ListenAction, RateAction, ActiveActions])
