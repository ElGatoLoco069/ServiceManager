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
    def get_operator(operator_value):
        """
        Localiza o operador recebido pelo frontend.

        Aceita:
        - ID do usuário
        - username do usuário
        """

        if not operator_value:
            return None

        operator_value = str(operator_value).strip()

        # Primeiro tenta localizar pelo ID
        if operator_value.isdigit():
            operator = User.objects.filter(
                pk=int(operator_value)
            ).first()

            if operator:
                return operator

        # Caso não seja ID ou não encontre pelo ID,
        # tenta localizar pelo username
        return User.objects.filter(
            username=operator_value
        ).first()

    @staticmethod
    def verify_schedule(request):

        try:
            errors = []

            items = json.loads(
                request.POST.get("schedule_items", "[]")
            )

            if not items:
                messages.warning(
                    request,
                    "Nenhum item foi encontrado para agendar!"
                )
                return None

            for item_data in items:

                if len(item_data) != 5:
                    errors.append(
                        "Foi encontrado um item de agendamento inválido."
                    )
                    continue

                item_id, date_value, time_value, status, operator_value = item_data

                item = ServiceRequestItem.objects.filter(
                    public_id=item_id
                ).first()

                if not item:
                    errors.append(
                        "Um dos serviços informados não foi encontrado."
                    )
                    continue

                # Item cancelado não precisa de data, hora ou operador
                if status == "canceled":
                    continue

                if date_value and not time_value:
                    errors.append(
                        f"É necessário informar o horário "
                        f"para o serviço {item.service}."
                    )

                if time_value and not date_value:
                    errors.append(
                        f"É necessário informar a data "
                        f"para o serviço {item.service}."
                    )

                if date_value and time_value and not operator_value:
                    errors.append(
                        f"É necessário informar o operador responsável "
                        f"pelo serviço {item.service}."
                    )

                if date_value and time_value and operator_value:

                    operator_user = DiaryService.get_operator(
                        operator_value
                    )

                    if not operator_user:
                        errors.append(
                            f"O operador selecionado para o serviço "
                            f"{item.service} não foi encontrado."
                        )

            return errors

        except json.JSONDecodeError:
            messages.error(
                request,
                "Os dados do agendamento são inválidos."
            )
            return None

        except Exception as e:
            messages.error(
                request,
                f"Erro ao realizar validação do agendamento! Erro: {e}"
            )
            return None

    @staticmethod
    @transaction.atomic
    def to_schedule(request, service_request_id):

        redirect_name = DiaryService.redirect_name(request)

        try:
            errors = DiaryService.verify_schedule(request)

            if errors is None:
                return redirect(redirect_name)

            if errors:
                for error in errors:
                    messages.warning(request, error)

                return redirect(redirect_name)

            service_request = ServiceRequest.objects.filter(
                public_id=service_request_id
            ).first()

            if not service_request:
                messages.error(
                    request,
                    "Solicitação de serviço não encontrada."
                )
                return redirect(redirect_name)

            itens = json.loads(
                request.POST.get("schedule_items", "[]")
            )

            for item_data in itens:

                if len(item_data) != 5:
                    continue

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
                    continue

                # =========================
                # ITEM CANCELADO
                # =========================

                if status == "canceled":

                    item.status = ServiceRequestItem.Status.CANCELED

                    item.scheduled_for = None

                    # Remove o operador do item cancelado
                    item.operator = None

                    item.updated_by = request.user

                    item.save(
                        update_fields=[
                            "status",
                            "scheduled_for",
                            "operator",
                            "updated_by",
                        ]
                    )

                    continue

                # =========================
                # ITEM AGENDADO
                # =========================

                if date_value and time_value:

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

                    scheduled_for = timezone.make_aware(
                        scheduled_for,
                        timezone.get_current_timezone(),
                    )

                    operator_user = DiaryService.get_operator(
                        operator_value
                    )

                    if not operator_user:
                        raise ValueError(
                            f"Operador '{operator_value}' não encontrado."
                        )

                    item.scheduled_for = scheduled_for
                    item.operator = operator_user

                    item.status = (
                        ServiceRequestItem.Status.SCHEDULED
                    )

                    item.updated_by = request.user

                    item.save(
                        update_fields=[
                            "scheduled_for",
                            "operator",
                            "status",
                            "updated_by",
                        ]
                    )

            # =========================
            # ATUALIZA STATUS DA SOLICITAÇÃO
            # =========================

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

                    service_request.status = (
                        ServiceRequest.Status.SCHEDULED
                    )

                else:

                    service_request.status = (
                        ServiceRequest.Status.REQUESTED
                    )

                service_request.save(
                    update_fields=[
                        "status",
                    ]
                )

            messages.success(
                request,
                f"Serviço {service_request.protocol} "
                f"atualizado com sucesso!"
            )

            return redirect(redirect_name)

        except json.JSONDecodeError:

            messages.error(
                request,
                "Erro ao interpretar os dados do agendamento."
            )

            return redirect(redirect_name)

        except Exception as e:

            messages.error(
                request,
                f"Erro ao agendar serviços! Erro: {e}"
            )

            return redirect(redirect_name)