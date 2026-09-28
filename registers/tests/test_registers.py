from unittest import expectedFailure
from unittest.mock import Mock, patch

from django.contrib.messages import get_messages
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from app.tests.helpers import make_request, make_service_type, make_user
from registers.models import ServiceType
from registers.services.registers import RegisterService


class ServiceTypeModelAndServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("register-manager")

    def test_model_string_ordering_and_metadata(self):
        second = make_service_type(self.user, "Zeladoria")
        first = make_service_type(self.user, "Arborização")
        self.assertEqual(str(first), "Arborização")
        self.assertEqual(list(ServiceType.objects.all()), [first, second])
        self.assertEqual(ServiceType._meta.verbose_name_plural, "Tipos de serviços")

    def test_get_and_read_form(self):
        service = make_service_type(self.user)
        self.assertEqual(list(RegisterService.get_service_type()), [service])
        request = make_request(data={"name": "Coleta", "default_unit": "kg", "is_active": "True"}, user=self.user)
        self.assertEqual(RegisterService.read_form(request), {"name": "Coleta", "default_unit": "kg", "is_active": "True"})

    def test_create_validation_is_strict_and_case_insensitive(self):
        make_service_type(self.user, "Coleta")
        request = make_request(user=self.user)
        errors = RegisterService.verify_form(request, {"name": "cOlEtA", "default_unit": " ", "is_active": "False"})
        self.assertIn("Serviço já cadastrado!", errors)
        self.assertIn("É necessario definir o status como ativo!", errors)
        self.assertIn("É necessario informar a unidade de medida!", errors)

        errors = RegisterService.verify_form(request, {"name": "", "default_unit": None, "is_active": "invalid"})
        self.assertIn("É necessario informar o nome do serviço!", errors)
        self.assertIn("É necessario informar se é Ativo ou Inativo!", errors)

    @expectedFailure
    def test_create_validation_normalizes_surrounding_whitespace_before_duplicate_check(self):
        make_service_type(self.user, "Coleta")
        errors = RegisterService.verify_form(
            make_request(user=self.user),
            {"name": " coleta ", "default_unit": "kg", "is_active": "True"},
        )
        self.assertIn("Serviço já cadastrado!", errors)

    def test_update_validation_excludes_current_service_and_detects_other_duplicate(self):
        own = make_service_type(self.user, "Own")
        make_service_type(self.user, "Other")
        request = make_request(user=self.user)
        self.assertEqual(RegisterService.verify_form(request, {"name": "Own", "default_unit": "u", "is_active": "True"}, own), [])
        self.assertIn("Serviço já cadastrado!", RegisterService.verify_form(request, {"name": "Other", "default_unit": "u", "is_active": "True"}, own))

    def test_validation_exception_returns_safe_redirect(self):
        class BrokenContext(dict):
            def get(self, key, default=None):
                raise RuntimeError("broken")

        response = RegisterService.verify_form(make_request(user=self.user), BrokenContext())
        self.assertEqual(response.url, reverse("list_services"))

    def test_save_service_type_handles_validation_success_and_database_error(self):
        invalid = make_request(data={"name": "", "default_unit": "u", "is_active": "True"}, user=self.user)
        self.assertEqual(RegisterService.save_service_type(invalid).url, reverse("list_services"))
        self.assertEqual(ServiceType.objects.count(), 0)

        valid = make_request(data={"name": "Poda", "default_unit": "hora", "is_active": "True"}, user=self.user)
        self.assertEqual(RegisterService.save_service_type(valid).url, reverse("list_services"))
        saved = ServiceType.objects.get()
        self.assertEqual(saved.created_by, self.user)
        self.assertTrue(saved.is_active)

        failing = make_request(data={"name": "Falha", "default_unit": "hora", "is_active": "True"}, user=self.user)
        with patch("registers.services.registers.ServiceType.objects.create", side_effect=RuntimeError("db")):
            self.assertEqual(RegisterService.save_service_type(failing).url, reverse("list_services"))

    def test_update_service_toggles_status_and_handles_validation_and_save_errors(self):
        service = make_service_type(self.user, "Poda", is_active=True)
        invalid = make_request(data={"name": "Poda", "default_unit": "", "is_active": "True"}, user=self.user)
        RegisterService.update_service_type(invalid, service.public_id)
        service.refresh_from_db()
        self.assertTrue(service.is_active)

        valid = make_request(data={"name": "Poda urbana", "default_unit": "hora", "is_active": "True"}, user=self.user)
        RegisterService.update_service_type(valid, service.public_id)
        service.refresh_from_db()
        self.assertFalse(service.is_active)
        self.assertEqual(service.name, "Poda urbana")
        self.assertEqual(service.updated_by, self.user)

        again = make_request(data={"name": "Poda urbana", "default_unit": "hora", "is_active": "False"}, user=self.user)
        RegisterService.update_service_type(again, service.public_id)
        service.refresh_from_db()
        self.assertTrue(service.is_active)

        with patch.object(ServiceType, "save", side_effect=RuntimeError("db")):
            self.assertEqual(RegisterService.update_service_type(again, service.public_id).url, reverse("list_services"))


class RegisterViewsTests(TestCase):
    def setUp(self):
        self.manager = make_user("register-view-manager")
        self.operator = make_user("register-view-operator", profile_type=Profile.ProfileType.OPERATOR)

    def test_all_views_require_authentication(self):
        cases = [
            ("get", reverse("list_services")),
            ("post", reverse("create_service")),
            ("post", reverse("update_service", args=["x"])),
        ]
        for method, url in cases:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("auth")))

    def test_operator_is_denied_from_all_register_endpoints(self):
        self.client.force_login(self.operator)
        for method, url in [
            ("get", reverse("list_services")),
            ("post", reverse("create_service")),
            ("post", reverse("update_service", args=["x"])),
        ]:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertRedirects(response, reverse("auth"), fetch_redirect_response=False)

    def test_manager_list_renders_services(self):
        make_service_type(self.manager, "Roçada")
        self.client.force_login(self.manager)
        response = self.client.get(reverse("list_services"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "list_services.html")
        self.assertContains(response, "Roçada")

    @patch("registers.views.RegisterService.save_service_type")
    def test_manager_create_delegates_to_service(self, save_service):
        self.client.force_login(self.manager)
        save_service.return_value = HttpResponseRedirect(reverse("list_services"))
        response = self.client.post(reverse("create_service"))
        self.assertIs(response, save_service.return_value)

    @patch("registers.views.RegisterService.update_service_type")
    def test_manager_update_delegates_uuid_to_service(self, update_service):
        self.client.force_login(self.manager)
        update_service.return_value = HttpResponseRedirect(reverse("list_services"))
        response = self.client.post(reverse("update_service", args=["public-id"]))
        self.assertIs(response, update_service.return_value)
        self.assertEqual(update_service.call_args.args[1], "public-id")

    def test_operator_superuser_is_allowed(self):
        superuser = make_user("register-super", profile_type=Profile.ProfileType.OPERATOR, is_superuser=True)
        self.client.force_login(superuser)
        self.assertEqual(self.client.get(reverse("list_services")).status_code, 200)
