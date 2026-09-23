from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import redirect, render

from accounts.models import Profile

User = get_user_model()


@staticmethod
def get_profile_user(request):

    try:

        user = User.objects.filter(username=request.user).first()

        if not user:
            messages.warning(request, "Usuario não encontrado!")
            return redirect("auth")

        profile = Profile.objects.filter(user=user).first()

        if not profile:
            messages.warning(request, "Perfil de usuario não encontrado!")
            return redirect("auth")

        context = {
            'user':user,
            'profile':profile,
        }

        return render(request, "profile.html", {'context':context})

    except Exception as e:
        messages.error(request, "Erro ao carregar perfil do usuario!")


