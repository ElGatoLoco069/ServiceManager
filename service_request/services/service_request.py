from django.contrib import messages
from django.shortcuts import redirect

from datetime import datetime
import random
import string
from decimal import Decimal

from service_request.models import ServiceRequest, ServiceRequestItem
from registers.models import ServiceType

class ServiceRequestService:

    @staticmethod
    def read_form(request):

        try:

            context = {
                "requester_name":request.POST.get("requester_name"),
                "requester_phone":request.POST.get("requester_phone"),
                "requester_document":request.POST.get("requester_document"),
                "requester_email":request.POST.get("requester_email"),
                "service_postal_code":request.POST.get("service_postal_code"),
                "service_address":request.POST.get("service_address"),
                "service_number":request.POST.get("service_number"),
                "service_neighborhood":request.POST.get("service_neighborhood"),
                "service_landmark":request.POST.get("service_landmark"),
                "services":request.POST.getlist("services"),
                "quantities":request.POST.getlist("quantities"),
                "units":request.POST.getlist("units"),
                "notes":request.POST.get("notes"),
            }

            return context

        except Exception as e:
            messages.error(request, f"Erro ao realizar leitura do formulario! Erro: {e}")
            return redirect("service_request_form")


    @staticmethod
    def verify_form(request, context):

        try:

            errors = []

            if not (context.get("requester_name") or "").strip():
                errors.append("É necessario informar o nome do solicitante!")

            if not (context.get("requester_phone") or "").strip():
                errors.append("É necessario informar o telefone do solicitante!")         

            if not (context.get("service_address") or "").strip():
                errors.append("É necessario informar o endereço do serviço!")

            if not (context.get("service_neighborhood") or "").strip():
                errors.append("É necessario informar o Bairro/Comunidade!")

            if not context['services']:
                errors.append("Informe pelo menos um item!")

            for qtd in context['quantities']:
                if Decimal(qtd) < 0.01:
                    errors.append("A quantidade não pode ser menor que 0.01!")


            return errors

        except Exception as e:
            messages.error(request, f"Erro ao validar formulario! Erro: {e}")
            return redirect("service_request_form")


    @staticmethod
    def generate_protocol():

        lyrics = string.ascii_uppercase
        lyrics = "".join(random.choice(lyrics) for _ in range(4))
            
        today = datetime.today().strftime("%Y%m%d")
        number = random.randrange(1000, 9999)

        protocol = f"{lyrics}-{today}-{number}"

        return protocol


    @staticmethod
    def save_form(request):

        context = ServiceRequestService.read_form(request)
        errors = ServiceRequestService.verify_form(request, context)
        protocol = ServiceRequestService.generate_protocol()

        if errors:
            for error in errors:
                messages.warning(request, error)
                return redirect("service_request_form")

        try:

            service_request = ServiceRequest.objects.create(
                protocol=protocol,
                requester_name=context['requester_name'],
                requester_phone=context['requester_phone'],
                requester_document=context['requester_document'],
                requester_email=context['requester_email'],
                service_postal_code=context['service_postal_code'],
                service_address=context['service_address'],
                service_number=context['service_number'],
                service_neighborhood=context['service_neighborhood'],
                service_landmark=context['service_landmark'],
                notes=context['notes'],
                created_by=request.user,
                updated_by=request.user,
            )

            for service_id, quantity, unit in zip(context["services"], context["quantities"], context["units"],):

                service_type = ServiceType.objects.filter(public_id=service_id).first()

                ServiceRequestItem.objects.create(
                    service_request=service_request,
                    service_id=service_type,
                    service=service_type.name,
                    amount=quantity,
                    unit=unit,
                    created_by=request.user,
                    updated_by=request.user,
                )

            messages.success(request, f"Solicitação {protocol} registrada com sucesso!")
            return redirect("service_request_form")


        except Exception as e:
            messages.error(request, f"Erro ao tentar salvar à solicitação de serviço! Erro: {e}")
            return redirect("service_request_form")









