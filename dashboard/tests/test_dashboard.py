from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from app.tests.helpers import make_service_item, make_service_request, make_service_type, make_user
from dashboard.services import DashboardService
from service_request.models import ServiceRequest, ServiceRequestItem


class DashboardServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("dashboard-manager")
        self.operator = make_user("dashboard-operator", profile_type=Profile.ProfileType.OPERATOR)
        self.service_type = make_service_type(self.user, "Limpeza de terreno", "hora")

    def create_request(self, protocol, request_status, item_status, scheduled_for=None):
        service_request = make_service_request(self.user, protocol, status=request_status)
        make_service_item(
            self.user,
            service_request,
            self.service_type,
            status=item_status,
            scheduled_for=scheduled_for,
        )
        return service_request

    def test_context_uses_current_request_and_schedule_data(self):
        today_at_ten = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        pending_request = self.create_request("SRV-PENDING", ServiceRequest.Status.REQUESTED, ServiceRequestItem.Status.PENDING)
        make_service_item(
            self.user,
            pending_request,
            self.service_type,
            service="Serviço amanhã",
            scheduled_for=today_at_ten + timedelta(days=1),
            status=ServiceRequestItem.Status.SCHEDULED,
        )
        self.create_request("SRV-SCHEDULED", ServiceRequest.Status.SCHEDULED, ServiceRequestItem.Status.SCHEDULED, today_at_ten)
        self.create_request("SRV-IN-PROGRESS", ServiceRequest.Status.IN_PROGRESS, ServiceRequestItem.Status.IN_PROGRESS, today_at_ten + timedelta(hours=1))
        self.create_request("SRV-COMPLETED", ServiceRequest.Status.COMPLETED, ServiceRequestItem.Status.COMPLETED, today_at_ten + timedelta(hours=2))

        context = DashboardService.get_context()

        self.assertEqual(context["new_requests_count"], 4)
        self.assertEqual(context["awaiting_count"], 1)
        self.assertEqual(context["scheduled_today_count"], 3)
        self.assertEqual(context["in_progress_count"], 1)
        self.assertEqual(context["completed_today_count"], 1)
        self.assertEqual(len(context["recent_requests"]), 4)
        self.assertEqual([item.status for item in context["awaiting_service_request"][0].pending_items], [ServiceRequestItem.Status.PENDING])
        self.assertIn(self.operator.profile, context["operators"])
        self.assertIsNotNone(context["generated_at"])

    def test_recent_requests_are_limited_to_five_newest(self):
        for index in range(7):
            make_service_request(self.user, f"SRV-{index}")
        context = DashboardService.get_context()
        self.assertEqual(context["recent_requests_count"], 5)
        self.assertEqual([request.protocol for request in context["recent_requests"]], ["SRV-6", "SRV-5", "SRV-4", "SRV-3", "SRV-2"])


class DashboardViewTests(TestCase):
    def setUp(self):
        self.manager = make_user("dashboard-view-manager")
        self.operator = make_user("dashboard-view-operator", profile_type=Profile.ProfileType.OPERATOR)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("auth")))

    def test_operator_is_denied_but_superuser_operator_is_allowed(self):
        self.client.force_login(self.operator)
        self.assertRedirects(self.client.get(reverse("home")), reverse("auth"), fetch_redirect_response=False)

        superuser = make_user("dashboard-super", profile_type=Profile.ProfileType.OPERATOR, is_superuser=True)
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(reverse("home")).status_code, 200)

    def test_home_renders_empty_states_without_demo_content(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "home.html")
        self.assertContains(response, "Nenhum serviço agendado para hoje")
        self.assertContains(response, "Nenhuma solicitação registrada")
        self.assertNotContains(response, "demonstração")

    def test_home_exposes_schedule_action_for_pending_requests(self):
        service_type = make_service_type(self.manager, "Vistoria")
        requests = []
        for index in range(3):
            service_request = make_service_request(self.manager, f"SRV-TO-SCHEDULE-{index}")
            make_service_item(self.manager, service_request, service_type)
            requests.append(service_request)
        self.client.force_login(self.manager)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-dashboard-schedule-dialog")
        self.assertContains(response, f'data-request-id="{requests[0].public_id}"')
        self.assertContains(response, 'name="return_to" value="home"')
