from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from service_request.models import ServiceRequest


class ServiceRequestViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="service-request-test-user",
            password="test-password",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_form_uses_service_request_route_and_template(self):
        response = self.client.get(reverse("service_request_form"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "service_request_form.html")
        self.assertContains(response, "Registrar solicitação de serviço")
        self.assertContains(response, reverse("create_service_request"))

    def test_create_service_request_persists_and_redirects_to_form(self):
        response = self.client.post(
            reverse("create_service_request"),
            {
                "requester_name": "Pessoa de Teste",
                "requester_phone": "(45) 99999-9999",
                "service_address": "Rua de Teste",
                "service_neighborhood": "Centro",
            },
        )

        self.assertRedirects(response, reverse("service_request_form"))
        self.assertEqual(ServiceRequest.objects.count(), 1)
        request = ServiceRequest.objects.get()
        self.assertEqual(request.requester_name, "Pessoa de Teste")
        self.assertEqual(request.created_by, self.user)
