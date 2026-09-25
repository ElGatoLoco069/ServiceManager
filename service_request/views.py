from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404


from registers.services.registers import RegisterService
from service_request.services.protocol import search_protocol
from service_request.services.service_request import ServiceRequestService
from service_request.models import ServiceRequestItemPhoto

@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class ServiceRequestFormView(View):

    def get(self, request):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")

        context = {
            "services":RegisterService.get_service_type(),
        }

        return render(request, "service_request_form.html", {"context":context})


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class CreateServiceRequestView(View):

    def get(self, request):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")

        context = {
            "services":RegisterService.get_service_type(),
        }

        return render(request, "service_request_form.html", {"context":context})

    def post(self, request):

        if request.user.profile.profile_type == "operator" and not request.user.is_superuser:
            messages.warning(request, "Você não possui permissão para acessar este modulo!")
            return redirect("auth")
        
        return ServiceRequestService.save_form(request)


class SearchProtocolView(View):

    def get(self, request):

        return render(request, "protocol_search.html")


class ProtocolDetailView(View):

    def get(self, request):

        return search_protocol(request)


@login_required(login_url="auth")
def view_protocol_attachment(request, attachment_id):
    attachment = get_object_or_404(
        ServiceRequestItemPhoto,
        public_id=attachment_id,
    )

    try:
        response = FileResponse(
            attachment.attachment.open("rb"),
            as_attachment=False,
            filename=attachment.attachment.name.split("/")[-1],
        )

        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"

        return response

    except FileNotFoundError:
        raise Http404