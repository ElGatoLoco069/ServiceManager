from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View

from registers.services.registers import RegisterService
# Create your views here.


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class ListServiceTypeView(View):

    def get(self, request):

        return render(request, "list_services.html", 
                      {
                          "services":RegisterService.get_service_type()
                    })


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class CreateServiceTypeView(View):

    def post(self, request):

        return RegisterService.save_service_type(request)


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class UpdateServiceTypeView(View):

    def post(self, request, uuid):

        return RegisterService.update_service_type(request, uuid)


