from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend
from .models import UserV1Link

from werkzeug.security import check_password_hash

class V1PasswordAuthBackend(ModelBackend):
    def authenticate(self, request, username, password):
        try:
            user = User.objects.get(username=username)
            flask_hash = user.v1_link.password_hash
            
            if flask_hash and check_password_hash(flask_hash, password):
                return user
            
        except (User.DoesNotExist, UserV1Link.DoesNotExist):
            pass
