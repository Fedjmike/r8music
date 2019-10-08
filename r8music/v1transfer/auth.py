import re
from werkzeug.security import check_password_hash

from django.contrib.auth.hashers import BasePasswordHasher

"""Users which have been transferred from the V1 database can login using
   their original passwords, which were hashed and stored in a format generated
   by Werkzeug. This module handles conversion into the Django format, and
   implements a "hasher" which verifies them."""

#Such as "pbkdf2:sha1:1000$<salt>$<hash>"
werkzeug_pattern = re.compile("(.*):(.*):(\d*)\$(.*)\$(.*)")
#Such as "werkzeug_pbkdf2_sha1$1000$<salt>$<hash>"
django_pattern = re.compile("(.*)_(.*)_(.*)\$(\d*)\$(.*)\$(.*)")

def werkzeug_pw_hash_to_django(pw_hash):
    groups = werkzeug_pattern.fullmatch(pw_hash).groups()
    return "werkzeug_{}_{}${}${}${}".format(*groups)

def django_pw_hash_to_werkzeug(pw_hash):
    werkzeug, *groups = django_pattern.fullmatch(pw_hash).groups()
    return "{}:{}:{}${}${}".format(*groups)

class WerkzeugHasher(BasePasswordHasher):
    algorithm = "werkzeug_pbkdf2_sha1"
    
    def verify(self, password, encoded):
        werkzeug_formatted = django_pw_hash_to_werkzeug(encoded)
        return check_password_hash(werkzeug_formatted, password)
