from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View

from service_request.services.service_request import ServiceRequestService
from registers.services.registers import RegisterService
from diary.services.diary_service import DiaryService

from field_operator.services.operator import get_all_operators

@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class DiaryView(View):

    def get(self, request):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")


        context = {
            "get_all":ServiceRequestService.get_all(),
            "get_awaiting_service_request":ServiceRequestService.get_awaiting_service_request(),
            "services":RegisterService.get_service_type(),
            "operators":get_all_operators()
        }

        return render(request, "diary.html", {"context":context,})


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class ScheduleServiceItemView(View):

    def get(self, request):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")


        context = {
            "get_all":ServiceRequestService.get_all(),
            "get_awaiting_service_request":ServiceRequestService.get_awaiting_service_request(),
            "services":RegisterService.get_service_type(),
        }

        return render(request, "diary.html", {"context":context,})


    def post(self, request, service_request_id):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")
        
        return DiaryService.to_schedule(request, service_request_id)