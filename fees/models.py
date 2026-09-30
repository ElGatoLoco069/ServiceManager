from django.db import models
from django.conf import settings

from registers.models import ServiceType

import uuid


class ServiceRate(models.Model):

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True
    )

    service = models.ForeignKey(ServiceType, on_delete=models.PROTECT, related_name="service_rates")

    description = models.TextField(null=True, blank=True)
    value = models.DecimalField()
    minimum_base_value = models.DecimalField(default=3)

    active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_rate_created",
        verbose_name="Criado por",
    )

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_rate_updated",
        verbose_name="Atualizado por",
    )

    class Meta:
        ordering = ["service"]
        verbose_name = "Taxa do serviço"
        verbose_name_plural = "Taxas de serviços"

    def __str__(self):
        return f"{self.service} - {self.value}"