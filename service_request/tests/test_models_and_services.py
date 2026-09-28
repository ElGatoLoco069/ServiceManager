from datetime import timedelta
from unittest import expectedFailure
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app.tests.helpers import make_request, make_service_item, make_service_request, make_service_type, make_user, tiny_upload
from service_request.models import ServiceRequest, ServiceRequestItem, ServiceRequestItemPhoto
from service_request.services.service_request import ServiceRequestService


class ServiceRequestModelTests(TestCase):
    def setUp(self):
        self.user = make_user("request-model-user")
        self.service_type = make_service_type(self.user)
        self.service_request = make_service_request(self.user, "MODEL-1")
        self.item = make_service_item(self.user, self.service_request, self.service_type)

    def test_strings_status_defaults_and_metadata(self):
        self.assertEqual(str(self.service_request), "MODEL-1")
        self.assertEqual(self.service_request.status, ServiceRequest.Status.REQUESTED)
        self.assertEqual(self.item.status, ServiceRequestItem.Status.PENDING)
        self.assertEqual(ServiceRequest._meta.ordering, ["-created_at"])

        photo = ServiceRequestItemPhoto.objects.create(service_request_item=self.item, image=tiny_upload(), created_by=self.user)
        self.assertEqual(str(photo), f"Foto - {self.item}")
        self.assertNotEqual(photo.public_id, self.item.public_id)


class ServiceRequestServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("request-service-user")
        self.service_type = make_service_type(self.user, "Coleta", "kg")

    def valid_context(self, **overrides):
        context = {
            "requester_name": "Pessoa",
            "requester_phone": "45999999999",
            "requester_document": "123.456.789-00",
            "requester_email": "pessoa@example.test",
            "service_postal_code": "85800-000",
            "service_address": "Rua A",
            "service_number": "10",
            "service_neighborhood": "Centro",
            "service_landmark": "Praça",
            "services": [str(self.service_type.public_id)],
            "quantities": ["2.50"],
            "units": ["kg"],
            "notes": "Observação",
        }
        context.update(overrides)
        return context

    def request_from_context(self, context):
        return make_request(data=context, user=self.user)

    def test_query_helpers(self):
        requested = make_service_request(self.user, "QUERY-1")
        scheduled = make_service_request(self.user, "QUERY-2", status=ServiceRequest.Status.SCHEDULED)
        self.assertEqual(list(ServiceRequestService.get_all()), [scheduled, requested])
        self.assertEqual(list(ServiceRequestService.get_awaiting_service_request()), [requested])

        item = make_service_item(self.user, scheduled, self.service_type, status=ServiceRequestItem.Status.IN_PROGRESS)
        self.assertEqual(list(ServiceRequestService.get_services_in_execution()), [item])

    @expectedFailure
    def test_scheduled_today_helper_matches_datetime_by_date(self):
        request = make_service_request(self.user, "TODAY-SCHEDULE")
        item = make_service_item(self.user, request, self.service_type, scheduled_for=timezone.now(), status=ServiceRequestItem.Status.SCHEDULED)
        self.assertEqual(list(ServiceRequestService.get_services_scheduled_today()), [item])

    @expectedFailure
    def test_completed_today_helper_matches_datetime_by_date(self):
        request = make_service_request(self.user, "TODAY-COMPLETE")
        item = make_service_item(self.user, request, self.service_type, status=ServiceRequestItem.Status.COMPLETED)
        self.assertEqual(list(ServiceRequestService.get_services_completed_today()), [item])

    def test_read_form_collects_scalars_and_repeated_fields(self):
        context = self.valid_context()
        request = self.request_from_context(context)
        result = ServiceRequestService.read_form(request)
        self.assertEqual(result["services"], context["services"])
        self.assertEqual(result["quantities"], context["quantities"])
        self.assertEqual(result["requester_name"], "Pessoa")

    def test_read_form_exception_returns_redirect(self):
        request = make_request(user=self.user)
        request.POST = None
        response = ServiceRequestService.read_form(request)
        self.assertEqual(response.url, reverse("service_request_form"))

    def test_validation_reports_required_fields_and_invalid_quantities(self):
        request = make_request(user=self.user)
        errors = ServiceRequestService.verify_form(request, self.valid_context(
            requester_name=" ", requester_phone="", service_address=None,
            service_neighborhood=" ", services=[], quantities=["0", "-1", "1000"],
        ))
        self.assertEqual(len(errors), 8)
        self.assertTrue(any("solicitante" in error for error in errors))
        self.assertTrue(any("quantidade" in error for error in errors))
        self.assertIn("A quantidade não pode ser maior que 999!", errors)
        self.assertEqual(ServiceRequestService.verify_form(request, self.valid_context()), [])

    def test_validation_exception_returns_redirect(self):
        response = ServiceRequestService.verify_form(make_request(user=self.user), self.valid_context(quantities=["not-decimal"]))
        self.assertEqual(response.url, reverse("service_request_form"))

    @patch("service_request.services.service_request.random.randrange", return_value=4321)
    @patch("service_request.services.service_request.random.choice", side_effect=list("ABCD"))
    @patch("service_request.services.service_request.datetime")
    def test_protocol_generation_has_stable_shape(self, mocked_datetime, _choice, _range):
        mocked_datetime.today.return_value.strftime.return_value = "20260925"
        self.assertEqual(ServiceRequestService.generate_protocol(), "ABCD-20260925-4321")

    @patch.object(ServiceRequestService, "generate_protocol", return_value="SAVE-1")
    def test_save_form_persists_request_items_audit_and_sanitized_document(self, _protocol):
        request = self.request_from_context(self.valid_context())
        response = ServiceRequestService.save_form(request)
        self.assertEqual(response.url, reverse("service_request_form"))
        service_request = ServiceRequest.objects.get(protocol="SAVE-1")
        self.assertEqual(service_request.requester_document, "12345678900")
        self.assertEqual(service_request.created_by, self.user)
        item = service_request.items.get()
        self.assertEqual(item.service_id, self.service_type)
        self.assertEqual(item.service, "Coleta")
        self.assertEqual(str(item.amount), "2.50")

    @patch.object(ServiceRequestService, "generate_protocol", return_value="INVALID-1")
    def test_save_form_stops_on_validation_errors(self, _protocol):
        request = self.request_from_context(self.valid_context(requester_name=""))
        self.assertEqual(ServiceRequestService.save_form(request).url, reverse("service_request_form"))
        self.assertFalse(ServiceRequest.objects.exists())

    @patch.object(ServiceRequestService, "generate_protocol", return_value="ERROR-1")
    def test_save_form_handles_missing_service_reference(self, _protocol):
        context = self.valid_context(services=["00000000-0000-0000-0000-000000000001"])
        request = self.request_from_context(context)
        self.assertEqual(ServiceRequestService.save_form(request).url, reverse("service_request_form"))
        self.assertTrue(list(get_messages(request)))

    @expectedFailure
    @patch.object(ServiceRequestService, "generate_protocol", return_value="ATOMIC-ERROR")
    def test_save_form_rolls_back_parent_when_an_item_cannot_be_created(self, _protocol):
        context = self.valid_context(services=["00000000-0000-0000-0000-000000000001"])
        ServiceRequestService.save_form(self.request_from_context(context))
        self.assertFalse(ServiceRequest.objects.filter(protocol="ATOMIC-ERROR").exists())

    def test_document_and_email_are_required_by_current_form_contract(self):
        errors = ServiceRequestService.verify_form(
            make_request(user=self.user),
            self.valid_context(requester_document=None, requester_email=""),
        )
        self.assertIn("É necessario informar o CPF ou CNPJ do solicitante!", errors)
        self.assertIn("É necessario informar o E-mail do solicitante!", errors)
