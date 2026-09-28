import ssl
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from ldap3.core.exceptions import LDAPException

from accounts.models import Profile
from accounts.services.accounts import AuthenticationService
from app.tests.helpers import make_request, make_user


User = get_user_model()


class AuthenticationFormAndRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_read_form_trims_only_username_and_validation_lists_missing_fields(self):
        request = make_request(data={"username": "  User  ", "password": "  secret  "})
        self.assertEqual(
            AuthenticationService.read_form(request),
            {"username": "user", "password": "  secret  "},
        )
        self.assertEqual(AuthenticationService.form_validate({}), [
            "Informe um usuário válido.",
            "Informe uma senha válida.",
        ])
        self.assertEqual(AuthenticationService.form_validate({"username": "u", "password": "p"}), [])

    def test_client_ip_defaults_to_remote_and_only_trusts_forwarded_when_enabled(self):
        request = make_request()
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.1, 10.0.0.5"
        self.assertEqual(AuthenticationService.get_client_ip(request), "10.0.0.5")

        with override_settings(RATE_LIMIT_TRUST_X_FORWARDED_FOR=True):
            self.assertEqual(AuthenticationService.get_client_ip(request), "203.0.113.1")
            request.META["HTTP_X_FORWARDED_FOR"] = "  "
            self.assertEqual(AuthenticationService.get_client_ip(request), "10.0.0.5")
            request.META.pop("HTTP_X_FORWARDED_FOR")
            self.assertEqual(AuthenticationService.get_client_ip(request), "10.0.0.5")
            request.META.pop("REMOTE_ADDR")
            self.assertEqual(AuthenticationService.get_client_ip(request), "unknown")

    def test_username_normalization_and_hashed_cache_key_do_not_leak_value(self):
        self.assertEqual(AuthenticationService.normalize_username("  JoÃO "), "joão")
        self.assertEqual(AuthenticationService.normalize_username(None), "")
        key = AuthenticationService.generate_rate_limit_key("username", " SecretUser ")
        self.assertTrue(key.startswith("authentication:rate-limit:username:"))
        self.assertNotIn("secretuser", key)
        self.assertEqual(key, AuthenticationService.generate_rate_limit_key("username", "secretuser"))

    @patch("accounts.services.accounts.time.time", return_value=100.0)
    def test_rate_limit_status_handles_missing_invalid_expired_and_active_values(self, _time):
        key = "rate-key"
        self.assertEqual(AuthenticationService.get_rate_limit_status(key), (False, 0))

        cache.set(f"{key}:blocked_until", "invalid")
        self.assertEqual(AuthenticationService.get_rate_limit_status(key), (False, 0))
        self.assertIsNone(cache.get(f"{key}:blocked_until"))

        cache.set(f"{key}:blocked_until", 99)
        cache.set(f"{key}:attempts", 3)
        self.assertEqual(AuthenticationService.get_rate_limit_status(key), (False, 0))
        self.assertIsNone(cache.get(f"{key}:attempts"))

        cache.set(f"{key}:blocked_until", 101.2)
        self.assertEqual(AuthenticationService.get_rate_limit_status(key), (True, 2))

    @patch("accounts.services.accounts.time.time", return_value=100.0)
    def test_failed_attempts_increment_block_and_report_existing_block(self, _time):
        key = "failure-key"
        self.assertEqual(AuthenticationService.register_failed_attempt(key, 2), (False, 0))
        self.assertEqual(AuthenticationService.register_failed_attempt(key, 2), (True, 300))
        self.assertEqual(AuthenticationService.register_failed_attempt(key, 2), (True, 300))

    @patch("accounts.services.accounts.cache")
    def test_failed_attempt_uses_fallback_when_cache_increment_is_unsupported(self, mocked_cache):
        mocked_cache.add.return_value = False
        mocked_cache.incr.side_effect = NotImplementedError
        mocked_cache.get.return_value = 1
        self.assertEqual(AuthenticationService.register_failed_attempt("key", 4), (False, 0))
        mocked_cache.set.assert_called_with("key:attempts", 2, timeout=300)

    def test_reset_user_rate_limit_ignores_empty_and_clears_both_user_keys(self):
        with patch("accounts.services.accounts.cache.delete") as delete:
            AuthenticationService.reset_user_rate_limit("")
            delete.assert_not_called()
            AuthenticationService.reset_user_rate_limit(" User ")
            self.assertEqual(delete.call_count, 2)

    def test_retry_time_and_message_cover_singular_plural_and_minimum(self):
        cases = {0: "1 segundo", 1: "1 segundo", 2: "2 segundos", 60: "1 minuto", 61: "1 minuto e 1 segundo", 122: "2 minutos e 2 segundos"}
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(AuthenticationService.format_retry_time(value), expected)
        self.assertIn("1 minuto", AuthenticationService.get_rate_limit_message(60))

        with patch("builtins.divmod", return_value=(0, 0)):
            self.assertEqual(AuthenticationService.format_retry_time(10), "1 segundo")

    def test_failure_count_policy(self):
        self.assertFalse(AuthenticationService.should_count_auth_failure({"success": True}))
        for code in AuthenticationService.RATE_LIMIT_IGNORED_ERROR_CODES:
            self.assertFalse(AuthenticationService.should_count_auth_failure({"success": False, "code": code}))
        self.assertTrue(AuthenticationService.should_count_auth_failure({"success": False, "code": "52e"}))

    @patch.object(AuthenticationService, "register_failed_attempt")
    def test_combined_rate_limit_uses_ip_and_optional_user(self, register):
        register.side_effect = [(False, 0), (True, 20)]
        self.assertEqual(AuthenticationService.register_rate_limit_failure("ip", "user"), (True, 20))
        self.assertEqual(register.call_count, 2)

        register.reset_mock(side_effect=True)
        register.side_effect = [(False, 0)]
        self.assertEqual(AuthenticationService.register_rate_limit_failure("ip", None), (False, 0))
        register.assert_called_once()


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        cache.clear()

    def post(self, data=None, **extra):
        payload = {"username": "person", "password": "secret"}
        payload.update(data or {})
        return self.client.post(reverse("auth"), payload, **extra)

    @patch.object(AuthenticationService, "get_rate_limit_status", return_value=(True, 90))
    @patch.object(AuthenticationService, "authenticate_ad")
    def test_ip_block_short_circuits_directory_authentication(self, authenticate_ad, _status):
        response = self.post(REMOTE_ADDR="198.51.100.2")
        self.assertRedirects(response, reverse("auth"))
        authenticate_ad.assert_not_called()

    @patch.object(AuthenticationService, "get_rate_limit_status", side_effect=[(False, 0), (True, 30)])
    @patch.object(AuthenticationService, "authenticate_ad")
    def test_user_block_short_circuits_directory_authentication(self, authenticate_ad, _status):
        response = self.post()
        self.assertRedirects(response, reverse("auth"))
        authenticate_ad.assert_not_called()

    @patch.object(AuthenticationService, "authenticate_ad")
    def test_invalid_form_does_not_call_directory(self, authenticate_ad):
        response = self.post({"username": " ", "password": " "})
        self.assertRedirects(response, reverse("auth"))
        authenticate_ad.assert_not_called()

    @patch.object(AuthenticationService, "authenticate_ad", return_value={"success": False, "message": "invalid", "code": "52e", "user": None})
    @patch.object(AuthenticationService, "register_rate_limit_failure", return_value=(False, 0))
    def test_normal_auth_failure_is_counted(self, register_failure, _authenticate_ad):
        response = self.post()
        self.assertRedirects(response, reverse("auth"))
        register_failure.assert_called_once()

    @patch.object(AuthenticationService, "authenticate_ad", return_value={"success": False, "message": "down", "code": "ldap_error", "user": None})
    @patch.object(AuthenticationService, "register_rate_limit_failure")
    def test_infrastructure_failure_is_not_counted(self, register_failure, _authenticate_ad):
        self.assertRedirects(self.post(), reverse("auth"))
        register_failure.assert_not_called()

    @patch.object(AuthenticationService, "authenticate_ad", return_value={"success": False, "message": "invalid", "code": "52e", "user": None})
    @patch.object(AuthenticationService, "register_rate_limit_failure", return_value=(True, 50))
    def test_failure_that_reaches_limit_returns_generic_limit_message(self, _register, _auth):
        self.assertRedirects(self.post(), reverse("auth"))

    @patch.object(AuthenticationService, "authenticate_ad", return_value={"success": True, "message": "", "code": None, "user": None})
    def test_directory_success_without_user_data_is_rejected(self, _authenticate_ad):
        self.assertRedirects(self.post(), reverse("auth"))
        self.assertFalse(User.objects.filter(username="person").exists())

    def successful_result(self):
        return {"success": True, "message": "", "code": None, "user": {"first_name": "Person", "last_name": "Test", "email": "person@example.test"}}

    @patch.object(AuthenticationService, "authenticate_ad")
    def test_username_is_lowercased_before_directory_authentication(self, authenticate_ad):
        authenticate_ad.return_value = self.successful_result()
        self.post({"username": "PERSON.UPPER"})
        authenticate_ad.assert_called_once_with(username="person.upper", password="secret")

    @patch.object(AuthenticationService, "authenticate_ad")
    def test_success_creates_local_operator_with_unusable_password_and_redirects_to_tasks(self, authenticate_ad):
        authenticate_ad.return_value = self.successful_result()
        response = self.post()
        self.assertRedirects(response, reverse("list_task"), fetch_redirect_response=False)
        user = User.objects.get(username="person")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.get_full_name(), "Person Test")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    @patch.object(AuthenticationService, "authenticate_ad")
    def test_success_updates_existing_user_and_honors_safe_next(self, authenticate_ad):
        user = make_user("person")
        original_password = user.password
        authenticate_ad.return_value = self.successful_result()
        response = self.post({"next": reverse("user_profile")})
        self.assertRedirects(response, reverse("user_profile"), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertEqual(user.password, original_password)
        self.assertEqual(user.email, "person@example.test")

    @patch.object(AuthenticationService, "authenticate_ad")
    def test_unsafe_next_is_rejected_and_operator_is_sent_to_tasks(self, authenticate_ad):
        user = make_user("person", profile_type=Profile.ProfileType.OPERATOR)
        authenticate_ad.return_value = self.successful_result()
        response = self.post({"next": "https://evil.example/steal"})
        self.assertRedirects(response, reverse("list_task"), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertEqual(user.first_name, "Person")

    @patch.object(AuthenticationService, "authenticate_ad")
    def test_superuser_operator_can_use_safe_redirect(self, authenticate_ad):
        make_user("person", profile_type=Profile.ProfileType.OPERATOR, is_superuser=True)
        authenticate_ad.return_value = self.successful_result()
        response = self.post({"next": reverse("home")})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    @patch.object(AuthenticationService, "authenticate_ad")
    def test_manager_without_safe_next_uses_home_fallback(self, authenticate_ad):
        make_user("person", profile_type=Profile.ProfileType.MANAGER)
        authenticate_ad.return_value = self.successful_result()
        response = self.post({"next": "https://evil.example/"})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_logout_service_requires_post_and_ends_session(self):
        user = make_user("logout-user")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("auth"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


class ActiveDirectoryUnitTests(TestCase):
    @patch("accounts.services.accounts.Connection")
    @patch("accounts.services.accounts.ServerPool")
    @patch("accounts.services.accounts.Server")
    @patch("accounts.services.accounts.Tls")
    @patch("accounts.services.accounts.DomainService.read_connection")
    @patch.dict("accounts.services.accounts.os.environ", {"CERTIFICATE": "ca.pem", "DOMAIN_CONTROL": "dc1", "DOMAIN_CONTROL02": "dc2"})
    def test_bind_failure_maps_ad_code_and_never_logs_password(self, read_connection, tls, server, pool, connection):
        read_connection.return_value = SimpleNamespace(domain_name="example.test", search_base="dc=example,dc=test")
        conn = connection.return_value
        conn.bind.return_value = False
        conn.bound = False
        conn.result = {"message": "AcceptSecurityContext error, data 533, v1", "description": "invalidCredentials"}

        result = AuthenticationService.authenticate_ad("alice", "top-secret")

        self.assertFalse(result["success"])
        self.assertEqual(result["code"], "533")
        self.assertEqual(result["message"], AuthenticationService.AD_AUTH_MESSAGES["533"])
        tls.assert_called_once_with(validate=ssl.CERT_REQUIRED, ca_certs_file="ca.pem")
        self.assertEqual(server.call_count, 2)
        pool.assert_called_once()
        self.assertEqual(connection.call_args.kwargs["user"], "alice@example.test")

    @patch.object(AuthenticationService, "get_ad_user_data", return_value={"first_name": "A", "last_name": "B", "email": "a@b"})
    @patch("accounts.services.accounts.Connection")
    @patch("accounts.services.accounts.DomainService.read_connection", return_value=SimpleNamespace(domain_name="example.test", search_base="dc=x"))
    def test_successful_bind_reads_user_and_unbinds(self, _settings, connection, get_data):
        conn = connection.return_value
        conn.bind.return_value = True
        conn.bound = True
        result = AuthenticationService.authenticate_ad("alice", "secret")
        self.assertTrue(result["success"])
        self.assertEqual(result["user"]["email"], "a@b")
        get_data.assert_called_once()
        conn.unbind.assert_called_once()

    def test_directory_exceptions_return_safe_codes(self):
        cases = [
            (LDAPException("ldap"), "ldap_error"),
            (ValueError("bad config"), "configuration_error"),
            (RuntimeError("unexpected"), "unexpected_error"),
        ]
        for error, code in cases:
            with self.subTest(code=code), patch("accounts.services.accounts.DomainService.read_connection", side_effect=error):
                result = AuthenticationService.authenticate_ad("alice", "secret")
                self.assertFalse(result["success"])
                self.assertEqual(result["code"], code)
                self.assertNotIn("secret", result["message"])

    def test_error_code_parser(self):
        self.assertIsNone(AuthenticationService.get_ad_error_code(None))
        self.assertIsNone(AuthenticationService.get_ad_error_code({"message": "no code"}))
        self.assertEqual(AuthenticationService.get_ad_error_code({"message": "DATA 52E, v"}), "52e")

    def test_user_data_search_escapes_filter_and_handles_missing_entry(self):
        conn = MagicMock(entries=[])
        conn.search.return_value = False
        result = AuthenticationService.get_ad_user_data(conn, "*)(uid=*)", "example.test", "dc=x")
        self.assertEqual(result, {"first_name": "*)(uid=*)", "last_name": "", "email": ""})
        search_filter = conn.search.call_args.kwargs["search_filter"]
        self.assertNotIn("*)(uid=*)", search_filter)

    def test_user_data_uses_display_name_fallback_and_attributes(self):
        class Attribute:
            def __init__(self, value):
                self.value = value

        entry = SimpleNamespace(
            displayName=Attribute("  Ana Souza  "),
            givenName=Attribute(None),
            sn=Attribute(""),
            mail=Attribute(" ana@example.test "),
        )
        conn = MagicMock(entries=[entry])
        conn.search.return_value = True
        result = AuthenticationService.get_ad_user_data(conn, "ana", "example.test", "dc=x")
        self.assertEqual(result, {"first_name": "Ana", "last_name": "Souza", "email": "ana@example.test"})

        entry.displayName = Attribute("Prince")
        result = AuthenticationService.get_ad_user_data(conn, "prince", "example.test", "dc=x")
        self.assertEqual(result["first_name"], "Prince")

        entry.displayName = Attribute("Ana Souza")
        entry.givenName = Attribute("Ana")
        entry.sn = Attribute("Souza")
        result = AuthenticationService.get_ad_user_data(conn, "ana", "example.test", "dc=x")
        self.assertEqual(result["first_name"], "Ana")

    def test_attribute_reader_handles_absent_none_and_string_values(self):
        self.assertEqual(AuthenticationService.get_ad_attr(SimpleNamespace(), "mail"), "")
        self.assertEqual(AuthenticationService.get_ad_attr(SimpleNamespace(mail=SimpleNamespace(value=None)), "mail"), "")
        self.assertEqual(AuthenticationService.get_ad_attr(SimpleNamespace(mail=SimpleNamespace(value=123)), "mail"), "123")
