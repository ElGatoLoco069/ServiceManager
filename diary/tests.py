import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from registers.models import ServiceType
from service_request.models import ServiceRequest, ServiceRequestItem


class ScheduleServiceItemViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="diary-schedule-test",
            password="test-password",
        )
        service_type = ServiceType.objects.create(
            name="Vistoria técnica",
            default_unit="unidade",
            created_by=self.user,
            updated_by=self.user,
        )
        self.service_request = ServiceRequest.objects.create(
            protocol="SRV-DASHBOARD-SCHEDULE",
            requester_name="Solicitante teste",
            requester_phone="47999999999",
            service_address="Rua de teste",
            service_neighborhood="Centro",
            created_by=self.user,
            updated_by=self.user,
        )
        self.item = ServiceRequestItem.objects.create(
            service_request=self.service_request,
            service_id=service_type,
            service=service_type.name,
            amount=1,
            unit="unidade",
            created_by=self.user,
            updated_by=self.user,
        )
        self.client.force_login(self.user)

    def test_schedule_from_dashboard_redirects_home_and_persists_item(self):
        schedule_date = timezone.localdate() + timedelta(days=1)
        payload = [[str(self.item.public_id), schedule_date.isoformat(), "09:30", "scheduled"]]

        response = self.client.post(
            reverse("schedule_request_service", args=[self.service_request.public_id]),
            {
                "schedule_items": json.dumps(payload),
                "return_to": "home",
            },
        )

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.item.refresh_from_db()
        self.service_request.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.SCHEDULED)
        self.assertEqual(timezone.localtime(self.item.scheduled_for).date(), schedule_date)
        self.assertEqual(timezone.localtime(self.item.scheduled_for).strftime("%H:%M"), "09:30")
        self.assertEqual(self.service_request.status, ServiceRequest.Status.SCHEDULED)

    def test_schedule_rejects_time_without_date_and_returns_to_dashboard(self):
        payload = [[str(self.item.public_id), "", "09:30", "pending"]]

        response = self.client.post(
            reverse("schedule_request_service", args=[self.service_request.public_id]),
            {
                "schedule_items": json.dumps(payload),
                "return_to": "home",
            },
        )

        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.PENDING)
        self.assertIsNone(self.item.scheduled_for)
