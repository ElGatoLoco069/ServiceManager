from django.db.models import Prefetch
from django.utils import timezone

from service_request.models import ServiceRequest, ServiceRequestItem
from field_operator.services.operator import get_all_operators

class DashboardService:

    @staticmethod
    def get_context():
        today = timezone.localdate()

        pending_items = ServiceRequestItem.objects.filter(
            status=ServiceRequestItem.Status.PENDING,
        ).order_by("created_at")
        awaiting_requests = list(
            ServiceRequest.objects.filter(items__status=ServiceRequestItem.Status.PENDING)
            .distinct()
            .prefetch_related(
                Prefetch("items", queryset=pending_items, to_attr="pending_items"),
            )
            .order_by("created_at")
        )

        today_schedule = list(
            ServiceRequestItem.objects.filter(
                scheduled_for__date=today,
                status__in=(
                    ServiceRequestItem.Status.SCHEDULED,
                    ServiceRequestItem.Status.IN_PROGRESS,
                    ServiceRequestItem.Status.COMPLETED,
                ),
            )
            .select_related("service_request", "operator")
            .prefetch_related(
                Prefetch(
                    "service_request__items",
                    queryset=ServiceRequestItem.objects.select_related("operator").order_by("created_at"),
                ),
            )
            .order_by("scheduled_for", "created_at")
        )

        recent_requests = list(
            ServiceRequest.objects.prefetch_related(
                Prefetch(
                    "items",
                    queryset=ServiceRequestItem.objects.select_related("operator").order_by("created_at"),
                ),
            ).order_by("-created_at")[:5]
        )

        context = {
            "generated_at": timezone.localtime(),
            "new_requests_count": ServiceRequest.objects.filter(
                created_at__date=today,
            ).count(),
            "awaiting_service_request": awaiting_requests,
            "awaiting_count": len(awaiting_requests),
            "today_schedule": today_schedule,
            "scheduled_today_count": len(today_schedule),
            "in_progress_count": ServiceRequestItem.objects.filter(
                status=ServiceRequestItem.Status.IN_PROGRESS,
            ).count(),
            "completed_today_count": ServiceRequestItem.objects.filter(
                status=ServiceRequestItem.Status.COMPLETED,
                updated_at__date=today,
            ).count(),
            "recent_requests": recent_requests,
            "recent_requests_count": len(recent_requests),
            "operators":get_all_operators(),
        }

        return context
