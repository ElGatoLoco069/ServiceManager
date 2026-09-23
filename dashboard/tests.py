from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.services import DashboardService
from registers.models import ServiceType
from service_request.models import ServiceRequest, ServiceRequestItem


class DashboardServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dashboard-test",
            password="test-password",
        )
        self.service_type = ServiceType.objects.create(
            name="Limpeza de terreno",
            default_unit="hora",
            created_by=self.user,
            updated_by=self.user,
        )

    def create_request(self, protocol, request_status, item_status, scheduled_for=None):
        service_request = ServiceRequest.objects.create(
            protocol=protocol,
            requester_name="Solicitante teste",
            requester_phone="47999999999",
            service_address="Rua de teste",
            service_neighborhood="Centro",
            status=request_status,
            created_by=self.user,
            updated_by=self.user,
        )
        ServiceRequestItem.objects.create(
            service_request=service_request,
            service_id=self.service_type,
            service=self.service_type.name,
            amount=2,
            unit="horas",
            scheduled_for=scheduled_for,
            status=item_status,
            created_by=self.user,
            updated_by=self.user,
        )
        return service_request

    def test_context_uses_current_request_and_schedule_data(self):
        today_at_ten = timezone.localtime().replace(
            hour=10,
            minute=0,
            second=0,
            microsecond=0,
        )
        pending_request = self.create_request(
            "SRV-PENDING",
            ServiceRequest.Status.REQUESTED,
            ServiceRequestItem.Status.PENDING,
        )
        ServiceRequestItem.objects.create(
            service_request=pending_request,
            service_id=self.service_type,
            service="Serviço já agendado",
            scheduled_for=today_at_ten + timedelta(days=1),
            status=ServiceRequestItem.Status.SCHEDULED,
        )
        self.create_request(
            "SRV-SCHEDULED",
            ServiceRequest.Status.SCHEDULED,
            ServiceRequestItem.Status.SCHEDULED,
            today_at_ten,
        )
        self.create_request(
            "SRV-IN-PROGRESS",
            ServiceRequest.Status.IN_PROGRESS,
            ServiceRequestItem.Status.IN_PROGRESS,
            today_at_ten + timedelta(hours=1),
        )
        self.create_request(
            "SRV-COMPLETED",
            ServiceRequest.Status.COMPLETED,
            ServiceRequestItem.Status.COMPLETED,
            today_at_ten + timedelta(hours=2),
        )

        context = DashboardService.get_context()

        self.assertEqual(context["new_requests_count"], 4)
        self.assertEqual(context["awaiting_count"], 1)
        self.assertEqual(context["scheduled_today_count"], 3)
        self.assertEqual(context["in_progress_count"], 1)
        self.assertEqual(context["completed_today_count"], 1)
        self.assertEqual(len(context["recent_requests"]), 4)
        self.assertEqual(
            [item.status for item in context["awaiting_service_request"][0].pending_items],
            [ServiceRequestItem.Status.PENDING],
        )

    def test_home_renders_empty_states_without_demo_content(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nenhum serviço agendado para hoje")
        self.assertContains(response, "Nenhuma solicitação registrada")
        self.assertNotContains(response, "demonstração")

    def test_home_exposes_schedule_action_for_each_pending_request(self):
        service_request = self.create_request(
            "SRV-TO-SCHEDULE",
            ServiceRequest.Status.REQUESTED,
            ServiceRequestItem.Status.PENDING,
        )
        self.create_request(
            "SRV-TO-SCHEDULE-2",
            ServiceRequest.Status.REQUESTED,
            ServiceRequestItem.Status.PENDING,
        )
        third_request = self.create_request(
            "SRV-TO-SCHEDULE-3",
            ServiceRequest.Status.REQUESTED,
            ServiceRequestItem.Status.PENDING,
        )
        item = service_request.items.get()
        self.client.force_login(self.user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-dashboard-schedule-open", count=5)
        self.assertContains(response, "data-dashboard-schedule-dialog")
        self.assertContains(response, f'data-request-id="{service_request.public_id}"', count=2)
        self.assertContains(response, f'data-request-id="{third_request.public_id}"', count=1)
        self.assertContains(response, f'data-item-id="{item.public_id}"')
        self.assertContains(
            response,
            reverse("schedule_request_service", args=[service_request.public_id]).replace(
                str(service_request.public_id),
                "REQUEST_ID",
            ),
        )
        self.assertContains(response, 'name="return_to" value="home"')
