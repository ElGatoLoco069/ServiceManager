from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.generic import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from dashboard.services import DashboardService

# Create your views here.

@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class HomeView(View):

    def get(self, request):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")

        return render(request, "home.html", {"context":DashboardService.get_context(),})