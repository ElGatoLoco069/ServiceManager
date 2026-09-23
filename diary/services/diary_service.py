from django.shortcuts import redirect
from django.contrib import messages
from datetime import date as datetime_date
from datetime import time as datetime_time
from datetime import datetime

from django.utils import timezone
import json

from service_request.models import ServiceRequest, ServiceRequestItem

class DiaryService:

    @staticmethod
    def redirect_name(request):
        return "home" if request.POST.get("return_to") == "home" else "view_diary"

    @staticmethod
    def verify_schedule(request):
        
        try:

            errors = []
            items = json.loads(request.POST.get("schedule_items", "[]"))

            if not items:
                messages.warning(request, "Nenhum item foi encontrado para agendar!")
                return None


            for item_id, date, time, status in items:
    
                item = ServiceRequestItem.objects.filter(public_id=item_id).first()
    
                if date and not time:
                    errors.append(f"É necessário informar o horário para o serviço {item.service}")

                if time and not date:
                    errors.append(f"É necessário informar a data para o serviço {item.service}")

            return errors
        
        except Exception as e:
            messages.error(request, f"Erro ao realizar validação do agendamento! Erro: {e}")
            return None


        

    @staticmethod
    def to_schedule(request, service_request_id):

        try:
            redirect_name = DiaryService.redirect_name(request)
            errors = DiaryService.verify_schedule(request)

            if errors is None:
                return redirect(redirect_name)

            if errors:
                for error in errors:
                    messages.warning(request, error)

                return redirect(redirect_name)

            service_request = ServiceRequest.objects.filter(public_id=service_request_id).first()

            itens = json.loads(
                request.POST.get("schedule_items", "[]")
            )

            notes = request.POST.get("notes")

            for item_id, date_value, time_value, status in itens:

                item = ServiceRequestItem.objects.filter(public_id=item_id, service_request=service_request).first()

                if not item:
                    continue

                # Item cancelado
                if status == "canceled":
                    item.status = ServiceRequestItem.Status.CANCELED
                    item.scheduled_for = None
                    item.updated_by = request.user
                    item.save()
                    continue

                # Item agendado
                if date_value and time_value:

                    scheduled_date = datetime_date.fromisoformat(date_value)
                    scheduled_time = datetime_time.fromisoformat(time_value)

                    scheduled_for = datetime.combine(
                        scheduled_date,
                        scheduled_time,
                    )

                    item.scheduled_for = timezone.make_aware(
                        scheduled_for,
                        timezone.get_current_timezone(),
                    )

                    item.status = ServiceRequestItem.Status.SCHEDULED
                    item.updated_by = request.user
                    item.save()

            itens_pendentes = ServiceRequestItem.objects.filter(
                service_request=service_request,
                status=ServiceRequestItem.Status.PENDING,
            )

            if not itens_pendentes.exists():

                itens_agendados = ServiceRequestItem.objects.filter(
                    service_request=service_request,
                    status=ServiceRequestItem.Status.SCHEDULED,
                )

                if itens_agendados.exists():
                    service_request.status = ServiceRequest.Status.SCHEDULED
                else:
                    service_request.status = ServiceRequest.Status.REQUESTED

                service_request.save()

            messages.success(request, f"Serviço {service_request.protocol} atualizado com sucesso!")

            return redirect(redirect_name)

        except Exception as e:
            messages.error(request, f"Erro ao agendar serviços! Erro: {e}")
            return redirect(DiaryService.redirect_name(request))






