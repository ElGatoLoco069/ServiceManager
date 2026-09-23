from django.shortcuts import render
from django.views.generic import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from field_operator.services.operator import get_my_taks, start_service, finish_service

@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class OperatorView(View):

    def get(self, request):

        context = {
            "my_tasks":get_my_taks(request)
        }

        return render(request, "operator_task.html", {"context":context})


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class StartServiceView(View):

    def post(self, request, service_id):

        return start_service(request, service_id)


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class FinishServiceView(View):

    def post(self, request, service_id):

        return finish_service(request, service_id)

