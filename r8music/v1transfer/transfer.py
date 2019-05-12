from django.contrib.auth.models import User
from r8music.profiles.models import UserSettings, UserProfile, UserRatingDescription, Followership

from r8music.v1transfer.models import UserV1Link

from r8music.v1.model import Model, UserType

class BaseTransferer:
    def __init__(self, model):
        self.model = model
        
class UserTransferer(BaseTransferer):
    def transfer_user(self, user):
        try:
            v1_link = UserV1Link.objects.get(old_id=user.id)
            return v1_link.user
        
        except UserV1Link.DoesNotExist:
            pass
        
        new_user = User.objects.create_user(
            username=user.name,
            email=user.email,
            date_joined=user.creation.datetime
            #No password provided, will be unable to login by built-in authenticator
        )
        
        if user.type == UserType.admin:
            new_user.is_superuser = new_user.is_staff = True
            new_user.save()
        
        #Store the Flask-generated password, which can be used to log in through
        #a custom authenticator
        (password_hash,) = self.model.query_unique("select pw_hash from users where id=?", user.id)

        UserV1Link.objects.create(
            user=new_user,
            old_id=user.id,
            password_hash=password_hash
        )
        
        UserSettings.objects.create(
            user=new_user,
            timezone=user.timezone,
            listen_implies_unsave=user.get_listen_implies_unsave()
        )

        UserProfile.objects.create(
            user=new_user,
            avatar_url=user.avatar_url
        )
        
        for rating, description in user.get_rating_descriptions().items():
            UserRatingDescription.objects.create(user=new_user.profile, rating=rating, description=description)
        
        #Transfer the followerships for the users this user follows
        for friendship in user.get_friendships():
            if friendship["follows"]:
                other_user = self.model.get_user(friendship["id"])
                #Transfer the followed user, if it hasn't already been.
                #The transfer of this user may be currently ongoing, but is
                #certain to have been completed up to the point of followerships.
                new_other_user = self.transfer_user(other_user)
                
                Followership.objects.create(
                    follower=new_user,
                    user=new_other_user,
                    creation=friendship["since"].datetime
                )
                
        return new_user
        
    def transfer_all_users(self):
        for (user_id,) in self.model.query("select id from users"):
            self.transfer_user(self.model.get_user(user_id))
