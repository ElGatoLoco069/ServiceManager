from django.db import models
from django.conf import settings

import uuid

# Create your models here.

class ServiceType(models.Model):

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(max_length=150, unique=True)

    default_unit = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        verbose_name="Unidade padrão"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_type_created",
        verbose_name="Criado por",
    )

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_type_updated",
        verbose_name="Atualizado por",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Tipo de serviço"
        verbose_name_plural = "Tipos de serviços"

    def __str__(self):
        return self.name
