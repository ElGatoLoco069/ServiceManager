from django.test import SimpleTestCase
from django.urls import resolve, reverse


class UrlConfigurationTests(SimpleTestCase):
    def test_all_named_routes_reverse_and_resolve(self):
        routes = {
            "auth_clean": (),
            "auth": (),
            "logout": (),
            "user_profile": (),
            "home": (),
            "list_services": (),
            "create_service": (),
            "update_service": ("service-id",),
            "view_diary": (),
            "schedule_request_service": ("request-id",),
            "service_request_form": (),
            "create_service_request": (),
            "consult_protocol": (),
            "protocol_detail": (),
            "view_protocol_attachment": ("00000000-0000-0000-0000-000000000001",),
            "list_task": (),
            "start_task": ("service-id",),
            "finish_task": ("service-id",),
            "vapid_public_key": (),
            "subscription": (),
        }

        for name, args in routes.items():
            with self.subTest(name=name):
                url = reverse(name, args=args)
                self.assertEqual(resolve(url).url_name, name)

    def test_operator_routes_keep_the_current_public_contract(self):
        self.assertEqual(reverse("start_task", args=["abc"]), "/opertor/start_task/abc/")
        self.assertEqual(reverse("finish_task", args=["abc"]), "/opertor/finish_task/abc/")
