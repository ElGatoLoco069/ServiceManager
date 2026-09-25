from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View

from registers.services.registers import RegisterService
# Create your views here.


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class ListServiceTypeView(View):

    def get(self, request):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")

        return render(request, "list_services.html", 
                      {
                          "services":RegisterService.get_service_type()
                    })


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class CreateServiceTypeView(View):

    def post(self, request):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")
        
        return RegisterService.save_service_type(request)


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class UpdateServiceTypeView(View):

    def post(self, request, uuid):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")
        
        return RegisterService.update_service_type(request, uuid)


