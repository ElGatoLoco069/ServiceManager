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



@staticmethod
def update_profile(request):

    user = request.user
    user = User.objects.filter(username=user).first()
    
    email = request.POST.get("email")
    department = request.POST.get("department")


    if not user:
        messages.warning(request, "Usuario não encontrado!")
        return redirect("auth")

    if email:
        user.email=email
        user.save()

    profile = Profile.objects.filter(user=user).first()

    if not profile:
        messages.warning(request, "Não foi possivel localizar o perfil do usuario!")
        return redirect("auth")

    if department:
        profile.department=department
        profile.save()

    if department or email:
        messages.success(request, "Informações do usuario atualizadas com sucesso!")
        return redirect("user_profile")


    return redirect("user_profile")









