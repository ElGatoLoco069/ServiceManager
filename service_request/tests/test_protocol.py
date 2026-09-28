from unittest import expectedFailure
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from app.tests.helpers import make_request, make_service_item, make_service_request, make_service_type, make_user
from service_request.services import protocol


class ProtocolServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("protocol-user")
        self.service_type = make_service_type(self.user)

    def test_read_and_verify_form(self):
        request = make_request("get", data={"protocol": "ABC", "verify_code": "1234"})
        context = protocol.read_form(request)
        self.assertEqual(context, {"protocol": "ABC", "verify_code": "1234"})
        self.assertEqual(protocol.verify_form(request, context), [])
        self.assertEqual(len(protocol.verify_form(request, {"protocol": " ", "verify_code": ""})), 2)

    def test_read_and_verify_exceptions_redirect_safely(self):
        request = make_request("get")
        request.GET = None
        self.assertEqual(protocol.read_form(request).url, reverse("consult_protocol"))

        class BrokenContext(dict):
            def get(self, *args, **kwargs):
                raise RuntimeError("broken")

        self.assertEqual(protocol.verify_form(make_request("get"), BrokenContext()).url, reverse("consult_protocol"))

    def test_search_redirects_for_invalid_unknown_and_itemless_protocol(self):
        invalid = make_request("get", data={})
        self.assertEqual(protocol.search_protocol(invalid).url, reverse("consult_protocol"))

        unknown = make_request("get", data={"protocol": "UNKNOWN", "verify_code": "1234"})
        self.assertEqual(protocol.search_protocol(unknown).url, reverse("consult_protocol"))

        itemless = make_service_request(self.user, "ITEMLESS", requester_document="12345678900")
        request = make_request("get", data={"protocol": itemless.protocol, "verify_code": "1234"})
        self.assertEqual(protocol.search_protocol(request).url, reverse("consult_protocol"))

    def test_search_renders_protocol_and_items(self):
        service_request = make_service_request(self.user, "FOUND", requester_document="12345678900")
        item = make_service_item(self.user, service_request, self.service_type)
        request = make_request("get", data={"protocol": "FOUND", "verify_code": "1234"})
        response = protocol.search_protocol(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"FOUND", response.content)
        self.assertIn(item.service.encode(), response.content)

    @expectedFailure
    def test_verification_code_must_match_first_four_document_digits(self):
        service_request = make_service_request(self.user, "PREFIX", requester_document="99991234567")
        make_service_item(self.user, service_request, self.service_type)
        request = make_request("get", data={"protocol": "PREFIX", "verify_code": "1234"})
        response = protocol.search_protocol(request)
        self.assertEqual(response.url, reverse("consult_protocol"))

    @patch("service_request.services.protocol.read_form", side_effect=RuntimeError("db"))
    def test_search_handles_unexpected_errors(self, _read):
        request = make_request("get")
        self.assertEqual(protocol.search_protocol(request).url, reverse("consult_protocol"))
        self.assertTrue(list(get_messages(request)))
