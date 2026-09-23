from django.db import models
from django.conf import settings


class Profile(models.Model):

    class ProfileType(models.TextChoices):
        OPERATOR = "operator", "Operador"
        MANAGER = "manager", "Gestor"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Usuário",
    )

    department = models.CharField(
        max_length=150,
        null=True,
        blank=True,
        verbose_name="Setor",
    )

    profile_type = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        default=ProfileType.OPERATOR,
        verbose_name="Perfil",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles_created",
        verbose_name="Criado por",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="profiles_updated",
        verbose_name="Atualizado por",
    )

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()

    