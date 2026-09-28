import io
import tempfile
from types import SimpleNamespace
from unittest import expectedFailure
from unittest.mock import MagicMock, Mock, patch

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from app.tests.helpers import make_service_item, make_service_request, make_service_type, make_user, tiny_upload
from service_request.models import ServiceRequestItemPhoto


class ServiceRequestViewsTests(TestCase):
    def setUp(self):
        self.manager = make_user("request-view-manager")
        self.operator = make_user("request-view-operator", profile_type=Profile.ProfileType.OPERATOR)

    def test_protected_form_endpoints_require_login(self):
        for method, url in [
            ("get", reverse("service_request_form")),
            ("get", reverse("create_service_request")),
            ("post", reverse("create_service_request")),
        ]:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("auth")))

    def test_operator_is_denied_from_form_and_create(self):
        self.client.force_login(self.operator)
        for method, url in [
            ("get", reverse("service_request_form")),
            ("get", reverse("create_service_request")),
            ("post", reverse("create_service_request")),
        ]:
            with self.subTest(url=url):
                self.assertRedirects(getattr(self.client, method)(url), reverse("auth"), fetch_redirect_response=False)

    def test_manager_form_and_create_get_render_services(self):
        service_type = make_service_type(self.manager, "Serviço visual")
        self.client.force_login(self.manager)
        for name in ("service_request_form", "create_service_request"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "service_request_form.html")
                self.assertContains(response, service_type.name)
                self.assertContains(response, 'name="requester_name" type="text"', html=False)
                self.assertContains(response, 'required maxlength="150"', html=False)
                self.assertContains(response, 'name="requester_document"', html=False)
                self.assertContains(response, 'data-mask-document required', html=False)
                self.assertContains(response, 'name="requester_email"', html=False)
                self.assertContains(response, 'type="email" autocomplete="email"', html=False)
                self.assertContains(response, 'data-service-neighborhood required', html=False)
                self.assertContains(response, 'min="0.01" max="999"', html=False)

    @patch("service_request.views.ServiceRequestService.save_form")
    def test_create_post_delegates_to_service(self, save_form):
        self.client.force_login(self.manager)
        save_form.return_value = HttpResponseRedirect(reverse("service_request_form"))
        response = self.client.post(reverse("create_service_request"))
        self.assertIs(response, save_form.return_value)

    def test_public_protocol_search_page_and_detail_delegate(self):
        response = self.client.get(reverse("consult_protocol"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "protocol_search.html")
        with patch("service_request.views.search_protocol", return_value=HttpResponse("ok")) as search:
            delegated = self.client.get(reverse("protocol_detail"), {"protocol": "X"})
            self.assertIs(delegated, search.return_value)

    def test_operator_superuser_can_access_form(self):
        superuser = make_user("request-super", profile_type=Profile.ProfileType.OPERATOR, is_superuser=True)
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(reverse("service_request_form")).status_code, 200)


class ProtocolAttachmentViewTests(TestCase):
    def setUp(self):
        self.user = make_user("attachment-view-user")
        self.client.force_login(self.user)

    def test_attachment_route_requires_login_and_returns_404_for_unknown_id(self):
        self.client.logout()
        url = reverse("view_protocol_attachment", args=["00000000-0000-0000-0000-000000000001"])
        self.assertTrue(self.client.get(url).url.startswith(reverse("auth")))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 404)

    @patch("service_request.views.get_object_or_404")
    def test_attachment_success_sets_security_headers(self, get_object):
        attachment_file = MagicMock()
        attachment_file.name = "folder/evidence.jpg"
        attachment_file.open.return_value = io.BytesIO(b"image")
        get_object.return_value = SimpleNamespace(attachment=attachment_file)
        response = self.client.get(reverse("view_protocol_attachment", args=["00000000-0000-0000-0000-000000000001"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("evidence.jpg", response["Content-Disposition"])

    @patch("service_request.views.get_object_or_404")
    def test_missing_file_is_translated_to_http_404(self, get_object):
        attachment_file = MagicMock()
        attachment_file.open.side_effect = FileNotFoundError
        get_object.return_value = SimpleNamespace(attachment=attachment_file)
        response = self.client.get(reverse("view_protocol_attachment", args=["00000000-0000-0000-0000-000000000001"]))
        self.assertEqual(response.status_code, 404)

    @expectedFailure
    def test_real_photo_model_can_be_served_by_attachment_route(self):
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        with override_settings(MEDIA_ROOT=media.name):
            service_type = make_service_type(self.user)
            service_request = make_service_request(self.user, "PHOTO-VIEW")
            item = make_service_item(self.user, service_request, service_type)
            photo = ServiceRequestItemPhoto.objects.create(service_request_item=item, image=tiny_upload(), created_by=self.user)
            response = self.client.get(reverse("view_protocol_attachment", args=[photo.public_id]))
            self.assertEqual(response.status_code, 200)
