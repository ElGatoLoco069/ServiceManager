from django.contrib import admin
from registers.models import ServiceType

# Register your models here.
admin.site.site_header = "JE3 Service Manager"
admin.site.site_title = "Service Manager Admin"
admin.site.index_title = "Gerenciamento do sistema"


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "name",
        "is_active",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    ]

    search_fields = [
        "name",
    ]

    readonly_fields = [
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    ]
