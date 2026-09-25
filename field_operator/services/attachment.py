from pathlib import Path
from django.db import transaction
from django.shortcuts import redirect
from django.contrib import messages

import logging

from service_request.models import ServiceRequestItem, ServiceRequestItemPhoto

logger = logging.getLogger(__name__)

@staticmethod
def validate_attachments(request, context):

    try:

        allowed_files = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}
        errors = []

        RECORD_LIMIT_MB = 10
        BYTE_RECORD_LIMIT = RECORD_LIMIT_MB * 1024 * 1024

        for attachment in context:

            extension = Path(attachment.name).suffix.lower()

            if extension not in allowed_files:
                errors.append(f"Arquivo {attachment.name} não permitido!")

            if attachment.size == 0:
                errors.append(f"Arquivo {attachment.name} está vazio!")

            if attachment.size > BYTE_RECORD_LIMIT:
                errors.append(f"A foto excede o limite de {RECORD_LIMIT_MB} MB!")


        return errors

    except Exception as e:
        messages.error(request, f"Erro ao validar anexos! Erro: {e}")
        return redirect("list_task")


@staticmethod
def save_attachments(request, context, parent_object):

    try:
        service_instance = ServiceRequestItem.objects.filter(
            public_id=parent_object
        ).first()

        if not service_instance:
            messages.warning(
                request,
                "Não foi possível adicionar o documento, pois a tarefa não foi encontrada."
            )
            return redirect("list_task")

        attachments = context

        if not attachments:
            messages.warning(
                request,
                "Nenhum documento foi selecionado."
            )
            return redirect("list_task")

        errors = validate_attachments(request, attachments)

        if errors:
            for error in errors:
                messages.warning(request, error)

            return redirect("list_task")

        with transaction.atomic():

            for attachment in attachments:
                ServiceRequestItemPhoto.objects.create(
                    service_request_item=service_instance,
                    image=attachment,
                    created_by=request.user,
                )

        return redirect("list_task")

    except Exception:
        logger.exception(
            "Erro ao salvar documentos da tarefa %s",
            parent_object
        )

        messages.error(
            request,
            "Não foi possível salvar o documento. "
            "Tente novamente ou entre em contato com o suporte."
        )

        return redirect("list_task")

    