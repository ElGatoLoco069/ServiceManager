from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View

from registers.services.registers import RegisterService
from service_request.services.service_request import ServiceRequestService

@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class ServiceRequestFormView(View):

    def get(self, request):

        context = {
            "services":RegisterService.get_service_type(),
        }

        return render(request, "service_request_form.html", {"context":context})


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class CreateServiceRequestView(View):

    def get(self, request):

        context = {
            "services":RegisterService.get_service_type(),
        }

        return render(request, "service_request_form.html", {"context":context})

    def post(self, request):

        return ServiceRequestService.save_form(request)



