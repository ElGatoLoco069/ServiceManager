from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import Profile


@receiver(user_logged_in)
def create_profile_on_login(sender, request, user, **kwargs):

    Profile.objects.get_or_create(
        user=user,
        defaults={
            "created_by": user,
            "updated_by": user,
        },
    )