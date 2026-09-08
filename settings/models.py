from django.db import models

# Create your models here.

class DomainSetting(models.Model):

    domain_name = models.CharField(max_length=255, unique=True, help_text="Nome de dominio do Active Directory")
    search_base = models.CharField(max_length=255, help_text="Base de pesquisa do Active Directory")

    is_active = models.BooleanField(default=True, help_text="Indica se o dominio esta ativo ou nao")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.domain_name







