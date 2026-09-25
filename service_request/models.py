from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

import uuid

from registers.models import ServiceType

User = get_user_model()

# Create your models here.

class ServiceRequest(models.Model):

    class Status(models.TextChoices):
        REQUESTED = "requested", "Solicitado"
        SCHEDULED = "scheduled", "Agendado"
        IN_PROGRESS = "in_progress", "Em andamento"
        COMPLETED = "completed", "Concluído"
        CANCELED = "canceled", "Cancelado"

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    protocol = models.CharField(max_length=50, unique=True)

    requester_name = models.CharField(max_length=150)
    requester_phone = models.CharField(max_length=15)
    requester_document = models.CharField(max_length=18, null=True, blank=True)
    requester_email = models.EmailField(null=True, blank=True)

    service_postal_code = models.CharField(max_length=10, null=True, blank=True)
    service_address = models.CharField(max_length=250)
    service_number = models.CharField(max_length=20, null=True, blank=True)
    service_neighborhood = models.CharField(max_length=150)
    service_landmark = models.CharField(max_length=250, null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_request_created",
        verbose_name="Criado por",
    )

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_request_updated",
        verbose_name="Atualizado por",
    )


    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Solicitação de serviço"
        verbose_name_plural = "Solicitações de serviços"

    def __str__(self):
        return self.protocol


class ServiceRequestItem(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SCHEDULED = "scheduled", "Agendado"
        IN_PROGRESS = "in_progress", "Em andamento"
        COMPLETED = "completed", "Concluído"
        CANCELED = "canceled", "Cancelado"

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    service_request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name="items"
    )

    service_id = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT
    )

    service = models.CharField(max_length=250)

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1
    )

    unit = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    scheduled_for = models.DateTimeField(
        null=True,
        blank=True
    )

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_service_items",
        null=True,
        blank=True,
        verbose_name="Operador",
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Serviço iniciado em"
    )

    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_items_started",
        verbose_name="Serviço iniciado por",
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Serviço finalizado em"
    )

    finished_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_items_finished",
        verbose_name="Serviço finalizado por",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_request_item_created",
        verbose_name="Criado por",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_request_item_updated",
        verbose_name="Atualizado por",
    )
    

class ServiceRequestItemPhoto(models.Model):

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    service_request_item = models.ForeignKey(
        ServiceRequestItem,
        on_delete=models.CASCADE,
        related_name="photos",
    )

    image = models.ImageField(
        upload_to="service_request_items/photos/"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Enviada em"
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="service_item_photos",
        verbose_name="Enviada por",
    )

    def __str__(self):
        return f"Foto - {self.service_request_item}"