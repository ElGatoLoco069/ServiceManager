import tempfile
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from app.tests.helpers import make_request, make_service_item, make_service_request, make_service_type, make_user, tiny_upload
from field_operator.services.operator import finish_service, get_all_operators, get_my_taks, start_service
from service_request.models import ServiceRequest, ServiceRequestItem, ServiceRequestItemPhoto


class OperatorServiceTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.manager = make_user("operator-manager")
        self.operator = make_user("operator-one", profile_type=Profile.ProfileType.OPERATOR)
        self.other = make_user("operator-two", profile_type=Profile.ProfileType.OPERATOR)
        self.service_type = make_service_type(self.manager)
        self.service_request = make_service_request(self.manager, "OPERATOR-1")
        self.item = make_service_item(self.manager, self.service_request, self.service_type, operator=self.operator, status=ServiceRequestItem.Status.SCHEDULED)

    def request(self, user=None, files=None):
        return make_request(user=user or self.operator, files=files)

    def test_operator_queries(self):
        self.assertEqual(set(get_all_operators()), {self.operator.profile, self.other.profile})
        request = self.request()
        self.assertEqual(list(get_my_taks(request)), [self.item])

    def test_start_rejects_missing_and_invalid_states(self):
        cases = [
            ("00000000-0000-0000-0000-000000000001", None, self.operator),
            (self.item.public_id, ServiceRequestItem.Status.CANCELED, self.operator),
            (self.item.public_id, ServiceRequestItem.Status.COMPLETED, self.operator),
            (self.item.public_id, ServiceRequestItem.Status.IN_PROGRESS, self.operator),
            (self.item.public_id, ServiceRequestItem.Status.SCHEDULED, self.other),
        ]
        for identifier, status, actor in cases:
            with self.subTest(status=status, actor=actor.username):
                if status:
                    self.item.status = status
                    self.item.save()
                response = start_service(self.request(actor), identifier)
                self.assertEqual(response.url, reverse("list_task"))
        self.item.refresh_from_db()

    def test_start_rejects_when_operator_already_has_in_progress_task(self):
        another_request = make_service_request(self.manager, "OPERATOR-2")
        make_service_item(self.manager, another_request, self.service_type, operator=self.operator, status=ServiceRequestItem.Status.IN_PROGRESS)
        response = start_service(self.request(), self.item.public_id)
        self.assertEqual(response.url, reverse("list_task"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.SCHEDULED)

    def test_start_success_updates_item_and_parent_request(self):
        response = start_service(self.request(), self.item.public_id)
        self.assertEqual(response.url, reverse("list_task"))
        self.item.refresh_from_db()
        self.service_request.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.IN_PROGRESS)
        self.assertEqual(self.item.started_by, self.operator)
        self.assertIsNotNone(self.item.started_at)
        self.assertEqual(self.service_request.status, ServiceRequest.Status.IN_PROGRESS)
        self.assertEqual(self.service_request.updated_by, self.operator)

    @patch("field_operator.services.operator.ServiceRequestItem.objects.filter", side_effect=RuntimeError("db"))
    def test_start_handles_unexpected_error(self, _filter):
        response = start_service(self.request(), self.item.public_id)
        self.assertEqual(response.url, reverse("list_task"))

    def test_finish_rejects_missing_unauthorized_invalid_state_and_missing_image(self):
        response = finish_service(self.request(), "00000000-0000-0000-0000-000000000001")
        self.assertEqual(response.url, reverse("list_task"))

        cases = [
            (self.other, ServiceRequestItem.Status.IN_PROGRESS, [tiny_upload()]),
            (self.operator, ServiceRequestItem.Status.CANCELED, [tiny_upload()]),
            (self.operator, ServiceRequestItem.Status.COMPLETED, [tiny_upload()]),
            (self.operator, ServiceRequestItem.Status.SCHEDULED, [tiny_upload()]),
            (self.operator, ServiceRequestItem.Status.IN_PROGRESS, []),
        ]
        for actor, status, files in cases:
            with self.subTest(actor=actor.username, status=status, files=bool(files)):
                self.item.status = status
                self.item.operator = self.operator
                self.item.save()
                request = self.request(actor, {"attachment": files})
                response = finish_service(request, self.item.public_id)
                self.assertEqual(response.url, reverse("list_task"))

    @patch("field_operator.services.operator.save_attachments")
    def test_finish_completes_item_and_parent_when_all_work_is_done(self, save):
        self.item.status = ServiceRequestItem.Status.IN_PROGRESS
        self.item.save()

        def persist(_request, _attachments, _public_id):
            ServiceRequestItemPhoto.objects.create(service_request_item=self.item, image=tiny_upload(), created_by=self.operator)

        save.side_effect = persist
        request = self.request(files={"attachment": [tiny_upload()]})
        response = finish_service(request, self.item.public_id)
        self.assertEqual(response.url, reverse("list_task"))
        self.item.refresh_from_db()
        self.service_request.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.COMPLETED)
        self.assertEqual(self.item.finished_by, self.operator)
        self.assertEqual(self.service_request.status, ServiceRequest.Status.COMPLETED)

    @patch("field_operator.services.operator.save_attachments")
    def test_finish_keeps_parent_open_when_another_item_remains(self, save):
        self.item.status = ServiceRequestItem.Status.IN_PROGRESS
        self.item.save()
        make_service_item(self.manager, self.service_request, self.service_type, service="Second", status=ServiceRequestItem.Status.PENDING)
        save.side_effect = lambda *_: ServiceRequestItemPhoto.objects.create(service_request_item=self.item, image=tiny_upload(), created_by=self.operator)
        finish_service(self.request(files={"attachment": [tiny_upload()]}), self.item.public_id)
        self.service_request.refresh_from_db()
        self.assertEqual(self.service_request.status, ServiceRequest.Status.REQUESTED)

    @patch("field_operator.services.operator.save_attachments")
    def test_finish_does_not_complete_without_persisted_photo(self, _save):
        self.item.status = ServiceRequestItem.Status.IN_PROGRESS
        self.item.save()
        finish_service(self.request(files={"attachment": [tiny_upload()]}), self.item.public_id)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.IN_PROGRESS)

    @patch("field_operator.services.operator.ServiceRequestItem.objects.filter", side_effect=RuntimeError("db"))
    def test_finish_handles_unexpected_error(self, _filter):
        self.assertEqual(finish_service(self.request(), self.item.public_id).url, reverse("list_task"))
