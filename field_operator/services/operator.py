from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.db import transaction

from accounts.models import Profile
from service_request.models import ServiceRequest, ServiceRequestItem, ServiceRequestItemPhoto
from field_operator.services.attachment import save_attachments

User = get_user_model()


@staticmethod
def get_all_operators():

    return Profile.objects.filter(profile_type=Profile.ProfileType.OPERATOR)


@staticmethod
def get_my_taks(request):

    operator = User.objects.filter(username=request.user).first()

    itens = ServiceRequestItem.objects.filter(operator=operator)

    return itens


@staticmethod
def start_service(request, service_id):

    try:

        service = ServiceRequestItem.objects.filter(public_id=service_id).first()

        if not service:
            messages.warning(request, "Serviço nao encontrado!")
            return redirect("list_task")

        if service.status == ServiceRequestItem.Status.CANCELED:
            messages.warning(request, "Não é possivel iniciar uma tarefa cancelada!")
            return redirect("list_task")

        if service.status == ServiceRequestItem.Status.COMPLETED:
            messages.warning(request, "Não é possivel iniciar uma tarefa concluida!")
            return redirect("list_task")

        if service.status == ServiceRequestItem.Status.IN_PROGRESS:
            messages.warning(request, "Essa tarefa ja esta em andamento!")
            return redirect("list_task")

        if ServiceRequestItem.objects.filter(operator=request.user, status=ServiceRequestItem.Status.IN_PROGRESS):
            messages.warning(request, "Você já possui uma tarefa em andamento!")
            return redirect("list_task")

        if service.operator != request.user:
            messages.warning(request, "Você não tem autorização para mexer nesta tarefa!")
            return redirect("list_task")



        service.status=ServiceRequestItem.Status.IN_PROGRESS
        service.started_at = timezone.now()
        service.started_by=request.user
        service.updated_by=request.user
        service.save()    

        service_request = service.service_request
        service_request.status = ServiceRequest.Status.IN_PROGRESS
        service_request.updated_by = request.user
        service_request.save()

        messages.success(request, "Serviço iniciado com sucesso!")
        return redirect("list_task")

    except Exception as e:
        messages.error(request, f"Erro ao tentar iniciar serviço! Erro {e}")
        return redirect("list_task")



@staticmethod
def finish_service(request, service_id):

    try:

        service = ServiceRequestItem.objects.filter(
            public_id=service_id
        ).first()

        if not service:
            messages.warning(
                request,
                "Serviço não encontrado!"
            )
            return redirect("list_task")

        if service.operator != request.user:
            messages.warning(
                request,
                "Você não possui permissão para concluir esta tarefa!"
            )
            return redirect("list_task")

        if service.status == ServiceRequestItem.Status.CANCELED:
            messages.warning(
                request,
                "Não é possível concluir uma tarefa cancelada!"
            )
            return redirect("list_task")

        if service.status == ServiceRequestItem.Status.COMPLETED:
            messages.warning(
                request,
                "Esta tarefa já foi concluída!"
            )
            return redirect("list_task")

        if service.status != ServiceRequestItem.Status.IN_PROGRESS:
            messages.warning(
                request,
                "A tarefa precisa estar em andamento para ser concluída!"
            )
            return redirect("list_task")

        attachments = request.FILES.getlist("attachment")

        if not attachments:
            messages.warning(
                request,
                "Para concluir a tarefa é necessário adicionar uma imagem!"
            )
            return redirect("list_task")


        save_attachments(request, attachments, service.public_id)

        if ServiceRequestItemPhoto.objects.filter(service_request_item=service).exists():

            service.status = ServiceRequestItem.Status.COMPLETED
            service.finished_at = timezone.now()
            service.finished_by = request.user
            service.updated_by = request.user

            service.save()

            if not ServiceRequestItem.objects.filter( service_request=service.service_request).exclude(
                status__in=[
                    ServiceRequestItem.Status.COMPLETED, ServiceRequestItem.Status.CANCELED,
                ]).exists():

                service_request = service.service_request
                service_request.status = ServiceRequest.Status.COMPLETED
                service_request.updated_by = request.user
                service_request.save()

            messages.success(
                request,
                "Tarefa concluída com sucesso! Bom trabalho!"
            )

        return redirect("list_task")

    except Exception as e:

        messages.error(
            request,
            f"Erro ao tentar finalizar tarefa! Erro: {e}"
        )
    
        return redirect("list_task")
