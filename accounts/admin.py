from django.contrib import admin

from accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "department",
        "profile_type",

        "updated_at",
    )

    list_filter = (
        "profile_type",

        "department",
    )

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "department",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
    )

    fieldsets = (
        ("Usuário", {
            "fields": (
                "user",
                "department",
                "profile_type",
            )
        }),

        ("Auditoria", {
            "fields": (
                "created_at",
                "created_by",
                "updated_at",
                "updated_by",
            ),
            "classes": ("collapse",),
        }),
    )

    list_select_related = ("user",)

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by:
            obj.created_by = request.user

        obj.updated_by = request.user

        super().save_model(request, obj, form, change)