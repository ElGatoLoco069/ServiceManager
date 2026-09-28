from unittest import expectedFailure
from unittest.mock import Mock, patch

from django.http import HttpResponse, HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from app.tests.helpers import make_request, make_user
from diary.views import ScheduleServiceItemView


class DiaryViewTests(TestCase):
    def setUp(self):
        self.manager = make_user("diary-view-manager")
        self.operator = make_user("diary-view-operator", profile_type=Profile.ProfileType.OPERATOR)

    def test_endpoints_require_authentication(self):
        for method, url in [
            ("get", reverse("view_diary")),
            ("post", reverse("schedule_request_service", args=["id"])),
        ]:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("auth")))

    def test_operator_is_denied_from_diary_endpoints(self):
        self.client.force_login(self.operator)
        for method, url in [
            ("get", reverse("view_diary")),
            ("post", reverse("schedule_request_service", args=["id"])),
        ]:
            with self.subTest(url=url):
                self.assertRedirects(getattr(self.client, method)(url), reverse("auth"), fetch_redirect_response=False)

    @patch("diary.views.render", return_value=HttpResponse("ok"))
    @patch("diary.views.get_all_operators", return_value=["operator"])
    @patch("diary.views.RegisterService.get_service_type", return_value=["service"])
    @patch("diary.views.ServiceRequestService.get_awaiting_service_request", return_value=["pending"])
    @patch("diary.views.ServiceRequestService.get_all", return_value=["all"])
    def test_diary_get_builds_complete_context(self, _all, _pending, _services, _operators, render):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("view_diary"))
        self.assertEqual(response.status_code, 200)
        context = render.call_args.args[2]["context"]
        self.assertEqual(context["operators"], ["operator"])
        self.assertEqual(context["get_all"], ["all"])

    @patch("diary.views.render", return_value=HttpResponse("ok"))
    @patch("diary.views.RegisterService.get_service_type", return_value=["service"])
    @patch("diary.views.ServiceRequestService.get_awaiting_service_request", return_value=["pending"])
    @patch("diary.views.ServiceRequestService.get_all", return_value=["all"])
    def test_schedule_get_renders_diary_context(self, _all, _pending, _services, render):
        request = make_request("get", user=self.manager)
        response = ScheduleServiceItemView().get(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(render.call_args.args[2]["context"]["get_all"], ["all"])

    def test_schedule_get_method_denies_operator_before_building_context(self):
        request = make_request("get", user=self.operator)
        response = ScheduleServiceItemView().get(request)
        self.assertEqual(response.url, reverse("auth"))

    @expectedFailure
    def test_schedule_get_route_accepts_its_declared_request_id(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse("schedule_request_service", args=["id"]))
        self.assertEqual(response.status_code, 200)

    @patch("diary.views.DiaryService.to_schedule")
    def test_schedule_post_delegates_request_and_id(self, to_schedule):
        self.client.force_login(self.manager)
        to_schedule.return_value = HttpResponseRedirect(reverse("view_diary"))
        response = self.client.post(reverse("schedule_request_service", args=["request-id"]))
        self.assertIs(response, to_schedule.return_value)
        self.assertEqual(to_schedule.call_args.args[1], "request-id")

    def test_operator_superuser_is_allowed(self):
        superuser = make_user("diary-super", profile_type=Profile.ProfileType.OPERATOR, is_superuser=True)
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(reverse("view_diary")).status_code, 200)
