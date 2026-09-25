from django.contrib import admin
from django.utils.html import format_html

from service_request.models import ServiceRequest, ServiceRequestItem, ServiceRequestItemPhoto

class ServiceRequestItemInline(admin.TabularInline):
    model = ServiceRequestItem
    extra = 0

    fields = (
        "service",
        "amount",
        "unit",
        "scheduled_for",
        "status",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    )

    readonly_fields = (
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    )


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):

    list_display = (
        "protocol",
        "requester_name",
        "requester_phone",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "protocol",
        "requester_name",
        "requester_document",
        "requester_phone",
        "requester_email",
        "service_address",
        "service_neighborhood",
    )

    readonly_fields = (
        "public_id",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    )

    fieldsets = (
        (
            "Solicitação",
            {
                "fields": (
                    "public_id",
                    "protocol",
                    "status",
                )
            },
        ),
        (
            "Solicitante",
            {
                "fields": (
                    "requester_name",
                    "requester_document",
                    "requester_phone",
                    "requester_email",
                )
            },
        ),
        (
            "Local do serviço",
            {
                "fields": (
                    "service_postal_code",
                    "service_address",
                    "service_number",
                    "service_neighborhood",
                    "service_landmark",
                )
            },
        ),
        (
            "Observações",
            {
                "fields": (
                    "notes",
                )
            },
        ),
        (
            "Auditoria",
            {
                "fields": (
                    "created_at",
                    "created_by",
                    "updated_at",
                    "updated_by",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),
    )

    inlines = [
        ServiceRequestItemInline,
    ]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user

        obj.updated_by = request.user

        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for instance in instances:

            if isinstance(instance, ServiceRequestItem):

                if not instance.pk:
                    instance.created_by = request.user

                instance.updated_by = request.user

            instance.save()

        for instance in formset.deleted_objects:
            instance.delete()

        formset.save_m2m()


@admin.register(ServiceRequestItem)
class ServiceRequestItemAdmin(admin.ModelAdmin):

    list_display = (
        "service_request",
        "service",
        "amount",
        "unit",
        "status",
        "scheduled_for",
    )

    list_filter = (
        "status",
        "scheduled_for",
        "created_at",
    )

    search_fields = (
        "service_request__protocol",
        "service_request__requester_name",
        "service",
    )

    readonly_fields = (
        "public_id",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    )

    autocomplete_fields = (
        "service_request",
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user

        obj.updated_by = request.user

        super().save_model(request, obj, form, change)


@admin.register(ServiceRequestItemPhoto)
class ServiceRequestItemPhotoAdmin(admin.ModelAdmin):

    list_display = (
        "public_id",
        "service_request_item",
        "created_by",
        "created_at",
        "image_preview",
    )

    list_filter = (
        "created_at",
    )

    search_fields = (
        "public_id",
        "service_request_item__service",
        "created_by__username",
        "created_by__first_name",
        "created_by__last_name",
    )

    readonly_fields = (
        "public_id",
        "created_at",
        "image_preview_large",
    )

    list_select_related = (
        "service_request_item",
        "created_by",
    )

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Documento",
            {
                "fields": (
                    "public_id",
                    "service_request_item",
                    "image",
                    "image_preview_large",
                )
            },
        ),
        (
            "Auditoria",
            {
                "fields": (
                    "created_by",
                    "created_at",
                )
            },
        ),
    )

    @admin.display(description="Prévia")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 60px; height: 60px; '
                'object-fit: cover; border-radius: 6px;" />',
                obj.image.url,
            )

        return "-"

    @admin.display(description="Prévia da imagem")
    def image_preview_large(self, obj):
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 500px; max-height: 400px; '
                'object-fit: contain; border-radius: 8px;" />'
                "</a>",
                obj.image.url,
                obj.image.url,
            )

        return "Nenhuma imagem enviada."

    