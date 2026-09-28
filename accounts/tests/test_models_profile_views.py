from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse

from accounts.admin import ProfileAdmin
from accounts.models import Profile
from accounts.services.profile import get_profile_user
from accounts.signals import create_profile_on_login
from app.tests.helpers import make_request, make_user


User = get_user_model()


class ProfileModelAndSignalTests(TestCase):
    def test_string_uses_full_name_then_username(self):
        full = make_user("full-name")
        full.first_name = "Maria"
        full.last_name = "Silva"
        full.save()
        plain = make_user("plain-user")

        self.assertEqual(str(full.profile), "Maria Silva")
        self.assertEqual(str(plain.profile), "plain-user")

    def test_login_signal_creates_profile_once_with_audit_fields(self):
        user = User.objects.create_user(username="signal-user")
        Profile.objects.filter(user=user).delete()

        create_profile_on_login(sender=User, request=None, user=user)
        create_profile_on_login(sender=User, request=None, user=user)

        profile = Profile.objects.get(user=user)
        self.assertEqual(Profile.objects.filter(user=user).count(), 1)
        self.assertEqual(profile.created_by, user)
        self.assertEqual(profile.updated_by, user)


class ProfileServiceAndViewTests(TestCase):
    def setUp(self):
        self.user = make_user("profile-user")

    def test_profile_service_renders_current_user(self):
        request = make_request("get", reverse("user_profile"), user=self.user)

        response = get_profile_user(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"profile-user", response.content)

    def test_profile_service_redirects_when_user_or_profile_is_missing(self):
        ghost = User(username="missing")
        request = make_request("get", user=ghost)
        self.assertEqual(get_profile_user(request).url, reverse("auth"))

        Profile.objects.filter(user=self.user).delete()
        request = make_request("get", user=self.user)
        self.assertEqual(get_profile_user(request).url, reverse("auth"))

    @patch("accounts.services.profile.User.objects.filter", side_effect=RuntimeError("boom"))
    def test_profile_service_handles_unexpected_errors(self, _filter):
        request = make_request("get", user=self.user)
        self.assertIsNone(get_profile_user(request))

    def test_authentication_page_preserves_next_without_authentication(self):
        response = self.client.get(reverse("auth"), {"next": reverse("home")})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "login.html")
        self.assertEqual(response.context["next"], reverse("home"))
        self.assertContains(response, 'style="text-transform: lowercase;"')

    @patch("accounts.views.AuthenticationService.authenticate")
    def test_authentication_post_delegates_to_service(self, authenticate):
        authenticate.return_value = HttpResponseRedirect(reverse("home"))
        response = self.client.post(reverse("auth"), {"username": "u", "password": "p"})
        self.assertIs(response, authenticate.return_value)

    def test_protected_profile_and_logout_require_login(self):
        for method, name in (("get", "user_profile"), ("post", "logout")):
            with self.subTest(name=name):
                response = getattr(self.client, method)(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("auth")))

    def test_profile_view_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("user_profile"))
        self.assertEqual(response.status_code, 200)

    @patch("accounts.views.AuthenticationService.logout_service")
    def test_logout_view_delegates_to_service(self, logout_service):
        self.client.force_login(self.user)
        logout_service.return_value = HttpResponseRedirect(reverse("auth"))
        response = self.client.post(reverse("logout"))
        self.assertIs(response, logout_service.return_value)


class ProfileAdminTests(TestCase):
    def test_save_model_populates_audit_fields_on_create_and_update(self):
        actor = make_user("admin-actor", is_superuser=True)
        target = make_user("admin-target")
        profile = target.profile
        profile.created_by = None
        model_admin = ProfileAdmin(Profile, admin.site)
        request = Mock(user=actor)

        with patch("django.contrib.admin.ModelAdmin.save_model") as parent_save:
            model_admin.save_model(request, profile, Mock(), change=False)
            self.assertEqual(profile.created_by, actor)
            self.assertEqual(profile.updated_by, actor)
            parent_save.assert_called_once()

        original_creator = target
        profile.created_by = original_creator
        with patch("django.contrib.admin.ModelAdmin.save_model"):
            model_admin.save_model(request, profile, Mock(), change=True)
        self.assertEqual(profile.created_by, original_creator)
        self.assertEqual(profile.updated_by, actor)
