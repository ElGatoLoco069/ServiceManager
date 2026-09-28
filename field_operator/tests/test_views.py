from unittest.mock import Mock, patch

from django.http import HttpResponse, HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from app.tests.helpers import make_user


class OperatorViewsTests(TestCase):
    def setUp(self):
        self.operator = make_user("operator-view", profile_type=Profile.ProfileType.OPERATOR)

    def test_all_views_require_login(self):
        for method, url in [
            ("get", reverse("list_task")),
            ("post", reverse("start_task", args=["id"])),
            ("post", reverse("finish_task", args=["id"])),
        ]:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("auth")))

    @patch("field_operator.views.render", return_value=HttpResponse("ok"))
    @patch("field_operator.views.get_my_taks", return_value=["task"])
    def test_task_list_renders_real_context(self, get_tasks, render):
        self.client.force_login(self.operator)
        response = self.client.get(reverse("list_task"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(render.call_args.args[2]["context"]["my_tasks"], ["task"])
        get_tasks.assert_called_once()

    @patch("field_operator.views.start_service")
    def test_start_view_delegates(self, start):
        self.client.force_login(self.operator)
        start.return_value = HttpResponseRedirect(reverse("list_task"))
        response = self.client.post(reverse("start_task", args=["public-id"]))
        self.assertIs(response, start.return_value)
        self.assertEqual(start.call_args.args[1], "public-id")

    @patch("field_operator.views.finish_service")
    def test_finish_view_delegates(self, finish):
        self.client.force_login(self.operator)
        finish.return_value = HttpResponseRedirect(reverse("list_task"))
        response = self.client.post(reverse("finish_task", args=["public-id"]))
        self.assertIs(response, finish.return_value)
        self.assertEqual(finish.call_args.args[1], "public-id")
