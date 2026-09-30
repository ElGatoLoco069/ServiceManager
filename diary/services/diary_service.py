from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction

from datetime import date as datetime_date
from datetime import time as datetime_time
from datetime import datetime

import json

from service_request.models import ServiceRequest, ServiceRequestItem
from notifications.services.push_notification import PushNotificationService


User = get_user_model()


class DiaryService:

    @staticmethod
    def redirect_name(request):
        return (
            "home"
            if request.POST.get("return_to") == "home"
            else "view_diary"
        )

    @staticmethod
    def get_operator(value):

        if not value:
            return None

        value = str(value).strip()

        # Procura primeiro pelo ID
        if value.isdigit():
            operator = User.objects.filter(pk=value).first()

            if operator:
                return operator

        # Caso contrário procura pelo username
        return User.objects.filter(
            username=value
        ).first()

    @staticmethod
    def get_schedule_items(request):

        items = json.loads(
            request.POST.get("schedule_items", "[]")
        )

        if not items:
            raise ValueError(
                "Nenhum item foi encontrado para agendar!"
            )

        return items

    @staticmethod
    def get_scheduled_for(date_value, time_value):

        scheduled_date = datetime_date.fromisoformat(
            date_value
        )

        scheduled_time = datetime_time.fromisoformat(
            time_value
        )

        scheduled_for = datetime.combine(
            scheduled_date,
            scheduled_time,
        )

        return timezone.make_aware(
            scheduled_for,
            timezone.get_current_timezone(),
        )

    @staticmethod
    def validate_item(item, date_value, time_value, status, operator_value):

        if status == "canceled":
            return None

        if date_value and not time_value:
            raise ValueError(
                f"É necessário informar o horário "
                f"para o serviço {item.service}."
            )

        if time_value and not date_value:
            raise ValueError(
                f"É necessário informar a data "
                f"para o serviço {item.service}."
            )

        if date_value and time_value and not operator_value:
            raise ValueError(
                f"É necessário informar o operador responsável "
                f"pelo serviço {item.service}."
            )

        if not date_value and not time_value:
            return None

        operator = DiaryService.get_operator(
            operator_value
        )

        if not operator:
            raise ValueError(
                f"Operador '{operator_value}' não encontrado."
            )

        return operator

    @staticmethod
    def notify_new_assignment(item, operator):

        title = "Nova tarefa atribuída"

        message = (
            f"Olá {operator.first_name}, uma nova tarefa foi atribuida à você! "
            f"{item.service}."
        )

        url = f"/operator/list_task/"

        # Só envia depois que a transação for confirmada.
        transaction.on_commit(
            lambda: PushNotificationService.send_to_user(
                user=operator,
                title=title,
                message=message,
                url=url,
                tag=f"service-{item.public_id}",
            ),
            print(f"Notificação enviada com sucesso! {operator}")
        )

    @staticmethod
    def cancel_item(item, user):

        item.status = ServiceRequestItem.Status.CANCELED
        item.scheduled_for = None
        item.operator = None
        item.updated_by = user

        item.save(
            update_fields=[
                "status",
                "scheduled_for",
                "operator",
                "updated_by",
            ]
        )

    @staticmethod
    def schedule_item(
        item,
        operator,
        date_value,
        time_value,
        user,
    ):

        previous_operator_id = item.operator_id

        item.scheduled_for = DiaryService.get_scheduled_for(
            date_value,
            time_value,
        )

        item.operator = operator
        item.status = ServiceRequestItem.Status.SCHEDULED
        item.updated_by = user

        item.save(
            update_fields=[
                "scheduled_for",
                "operator",
                "status",
                "updated_by",
            ]
        )

        # Só notifica se realmente houve uma nova atribuição.
        if previous_operator_id != operator.pk:
            DiaryService.notify_new_assignment(
                item,
                operator,
            )

    @staticmethod
    def update_request_status(service_request):

        items = ServiceRequestItem.objects.filter(
            service_request=service_request
        )

        # Enquanto existir item pendente,
        # não altera o status geral.
        if items.filter(
            status=ServiceRequestItem.Status.PENDING
        ).exists():
            return

        if items.filter(
            status=ServiceRequestItem.Status.SCHEDULED
        ).exists():

            new_status = ServiceRequest.Status.SCHEDULED

        else:

            new_status = ServiceRequest.Status.REQUESTED

        if service_request.status != new_status:

            service_request.status = new_status

            service_request.save(
                update_fields=["status"]
            )

    @staticmethod
    def to_schedule(request, service_request_id):

        redirect_name = DiaryService.redirect_name(request)

        try:

            items = DiaryService.get_schedule_items(request)

            service_request = ServiceRequest.objects.filter(
                public_id=service_request_id
            ).first()

            if not service_request:
                raise ValueError(
                    "Solicitação de serviço não encontrada."
                )

            with transaction.atomic():

                for item_data in items:

                    if len(item_data) != 5:
                        raise ValueError(
                            "Foi encontrado um item de "
                            "agendamento inválido."
                        )

                    (
                        item_id,
                        date_value,
                        time_value,
                        status,
                        operator_value,
                    ) = item_data

                    item = ServiceRequestItem.objects.filter(
                        public_id=item_id,
                        service_request=service_request,
                    ).first()

                    if not item:
                        raise ValueError(
                            "Um dos serviços informados "
                            "não foi encontrado."
                        )

                    operator = DiaryService.validate_item(
                        item=item,
                        date_value=date_value,
                        time_value=time_value,
                        status=status,
                        operator_value=operator_value,
                    )

                    # CANCELADO
                    if status == "canceled":

                        DiaryService.cancel_item(
                            item,
                            request.user,
                        )

                        continue

                    # AGENDADO
                    if date_value and time_value:

                        DiaryService.schedule_item(
                            item=item,
                            operator=operator,
                            date_value=date_value,
                            time_value=time_value,
                            user=request.user,
                        )

                DiaryService.update_request_status(
                    service_request
                )

            messages.success(request, f"Serviço {service_request.protocol} "
                f"atualizado com sucesso!")

        except json.JSONDecodeError:
            messages.error(request, "Os dados do agendamento são inválidos.")

        except ValueError as error:

            messages.warning(
                request,
                str(error)
            )

        except Exception as error:

            messages.error(
                request,
                f"Erro ao agendar serviços! Erro: {error}"
            )

        return redirect(redirect_name)


    