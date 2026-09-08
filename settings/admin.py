from django.contrib import admin
from settings.models import DomainSetting


# Register your models here.

@admin.register(DomainSetting)
class DomainSettingAdmin(admin.ModelAdmin):
    list_display = ('domain_name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('domain_name', 'server_ip')