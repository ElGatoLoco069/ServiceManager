import tempfile
from unittest.mock import Mock, patch

from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from app.tests.helpers import make_request, make_service_item, make_service_request, make_service_type, make_user, tiny_upload
from field_operator.services.attachment import save_attachments, validate_attachments
from service_request.models import ServiceRequestItemPhoto


class AttachmentServiceTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = make_user("attachment-user")
        service_type = make_service_type(self.user)
        service_request = make_service_request(self.user, "ATTACH-1")
        self.item = make_service_item(self.user, service_request, service_type)

    def test_validation_accepts_supported_files_and_reports_each_invalid_condition(self):
        request = make_request(user=self.user)
        valid = [tiny_upload("photo.JPG"), SimpleUploadedFile("report.pdf", b"pdf")]
        self.assertEqual(validate_attachments(request, valid), [])

        empty = SimpleUploadedFile("empty.png", b"")
        invalid = SimpleUploadedFile("script.exe", b"x")
        oversized = Mock(name="large.jpg", size=10 * 1024 * 1024 + 1)
        oversized.name = "large.jpg"
        errors = validate_attachments(request, [empty, invalid, oversized])
        self.assertTrue(any("vazio" in error for error in errors))
        self.assertTrue(any("não permitido" in error for error in errors))
        self.assertTrue(any("excede" in error for error in errors))

    def test_validation_exception_returns_redirect(self):
        class BrokenAttachment:
            @property
            def name(self):
                raise RuntimeError("broken")

        response = validate_attachments(make_request(user=self.user), [BrokenAttachment()])
        self.assertEqual(response.url, reverse("list_task"))

    def test_save_rejects_missing_task_empty_selection_and_validation_errors(self):
        request = make_request(user=self.user)
        missing = save_attachments(request, [tiny_upload()], "00000000-0000-0000-0000-000000000001")
        self.assertEqual(missing.url, reverse("list_task"))
        self.assertEqual(save_attachments(request, [], self.item.public_id).url, reverse("list_task"))
        invalid = save_attachments(request, [SimpleUploadedFile("bad.exe", b"x")], self.item.public_id)
        self.assertEqual(invalid.url, reverse("list_task"))
        self.assertEqual(ServiceRequestItemPhoto.objects.count(), 0)

    def test_save_persists_all_valid_attachments_with_audit_user(self):
        request = make_request(user=self.user)
        response = save_attachments(request, [tiny_upload("one.jpg"), tiny_upload("two.png")], self.item.public_id)
        self.assertEqual(response.url, reverse("list_task"))
        self.assertEqual(ServiceRequestItemPhoto.objects.count(), 2)
        self.assertEqual(set(ServiceRequestItemPhoto.objects.values_list("created_by", flat=True)), {self.user.pk})

    @patch("field_operator.services.attachment.ServiceRequestItemPhoto.objects.create", side_effect=RuntimeError("storage"))
    def test_save_handles_storage_exception_without_leaking_details(self, _create):
        request = make_request(user=self.user)
        response = save_attachments(request, [tiny_upload()], self.item.public_id)
        self.assertEqual(response.url, reverse("list_task"))
        message = str(list(get_messages(request))[0])
        self.assertIn("Não foi possível salvar", message)
        self.assertNotIn("storage", message)
