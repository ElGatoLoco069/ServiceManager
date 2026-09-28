import json
from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from django.urls import reverse
from pywebpush import WebPushException

from app.tests.helpers import make_user
from notifications.models import PushSubscription
from notifications.services.push_notification import PushNotificationService


class PushSubscriptionModelTests(TestCase):
    def test_string_identifies_user(self):
        user = make_user("push-user")
        subscription = PushSubscription.objects.create(user=user, endpoint="https://push/1", p256dh="key", auth="auth")
        self.assertEqual(str(subscription), "Push - push-user")


class NotificationViewsTests(TestCase):
    def setUp(self):
        self.user = make_user("notification-user")
        self.other = make_user("notification-other")

    def test_views_require_authentication(self):
        for method, url in [("get", reverse("vapid_public_key")), ("post", reverse("subscription")), ("delete", reverse("subscription"))]:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("auth")))

    @override_settings(VAPID_PUBLIC_KEY=None)
    def test_public_key_reports_missing_configuration(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("vapid_public_key"))
        self.assertEqual(response.status_code, 503)
        self.assertIn("error", response.json())

    @override_settings(VAPID_PUBLIC_KEY="public-key")
    def test_public_key_is_returned_to_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("vapid_public_key"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"public_key": "public-key"})

    def test_subscription_post_rejects_invalid_shapes_and_json(self):
        self.client.force_login(self.user)
        invalid_payloads = [
            {},
            {"endpoint": 1, "keys": {"p256dh": "p", "auth": "a"}},
            {"endpoint": " ", "keys": {"p256dh": "p", "auth": "a"}},
            {"endpoint": "https://push", "keys": None},
            {"endpoint": "https://push", "keys": {"p256dh": "", "auth": "a"}},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(reverse("subscription"), data=json.dumps(payload), content_type="application/json")
                self.assertEqual(response.status_code, 400)
        response = self.client.post(reverse("subscription"), data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        response = self.client.generic("POST", reverse("subscription"), data=b"\xff", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_subscription_is_created_then_updated_and_can_change_owner(self):
        payload = {"endpoint": "https://push/one", "keys": {"p256dh": "p1", "auth": "a1"}}
        self.client.force_login(self.user)
        created = self.client.post(reverse("subscription"), data=json.dumps(payload), content_type="application/json")
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.json()["created"])

        payload["keys"] = {"p256dh": "p2", "auth": "a2"}
        self.client.force_login(self.other)
        updated = self.client.post(reverse("subscription"), data=json.dumps(payload), content_type="application/json")
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(updated.json()["created"])
        subscription = PushSubscription.objects.get(endpoint=payload["endpoint"])
        self.assertEqual(subscription.user, self.other)
        self.assertEqual(subscription.p256dh, "p2")

    def test_delete_validates_json_and_only_deletes_current_users_endpoint(self):
        own = PushSubscription.objects.create(user=self.user, endpoint="https://push/own", p256dh="p", auth="a")
        other = PushSubscription.objects.create(user=self.other, endpoint="https://push/other", p256dh="p", auth="a")
        self.client.force_login(self.user)

        self.assertEqual(self.client.delete(reverse("subscription"), data=json.dumps({}), content_type="application/json").status_code, 400)
        self.assertEqual(self.client.delete(reverse("subscription"), data="{", content_type="application/json").status_code, 400)
        malformed = self.client.generic("DELETE", reverse("subscription"), data=b"\xff", content_type="application/json")
        self.assertEqual(malformed.status_code, 400)

        not_owned = self.client.delete(reverse("subscription"), data=json.dumps({"endpoint": other.endpoint}), content_type="application/json")
        self.assertFalse(not_owned.json()["deleted"])
        deleted = self.client.delete(reverse("subscription"), data=json.dumps({"endpoint": own.endpoint}), content_type="application/json")
        self.assertTrue(deleted.json()["deleted"])
        self.assertFalse(PushSubscription.objects.filter(pk=own.pk).exists())
        self.assertTrue(PushSubscription.objects.filter(pk=other.pk).exists())


@override_settings(
    VAPID_PRIVATE_KEY="private-key",
    VAPID_CLAIMS={"sub": "mailto:test@example.test"},
)
class PushNotificationServiceTests(TestCase):
    def setUp(self):
        self.user = make_user("push-service-user")

    def subscription(self, suffix="one"):
        return PushSubscription.objects.create(user=self.user, endpoint=f"https://push/{suffix}", p256dh=f"p-{suffix}", auth=f"a-{suffix}")

    @patch("notifications.services.push_notification.webpush")
    def test_no_subscription_returns_false_without_network(self, webpush):
        self.assertFalse(PushNotificationService.send_to_user(self.user, "Title", "Message"))
        webpush.assert_not_called()

    @patch("notifications.services.push_notification.webpush")
    def test_success_sends_expected_payload_and_options(self, webpush):
        subscription = self.subscription()
        result = PushNotificationService.send_to_user(self.user, "Title", "Message", "/target", "tag-1")
        self.assertTrue(result)
        kwargs = webpush.call_args.kwargs
        self.assertEqual(kwargs["subscription_info"]["endpoint"], subscription.endpoint)
        self.assertEqual(json.loads(kwargs["data"]), {"title": "Title", "message": "Message", "url": "/target", "tag": "tag-1"})
        self.assertEqual(kwargs["vapid_private_key"], "private-key")
        self.assertEqual(kwargs["ttl"], 3600)
        self.assertEqual(kwargs["timeout"], 10)

    @patch("notifications.services.push_notification.webpush")
    def test_expired_webpush_subscription_is_deleted(self, webpush):
        subscription = self.subscription()
        webpush.side_effect = WebPushException("gone", response=Mock(status_code=410))
        self.assertFalse(PushNotificationService.send_to_user(self.user, "T", "M"))
        self.assertFalse(PushSubscription.objects.filter(pk=subscription.pk).exists())

    @patch("notifications.services.push_notification.webpush")
    def test_non_expired_webpush_error_keeps_subscription(self, webpush):
        subscription = self.subscription()
        webpush.side_effect = WebPushException("server", response=Mock(status_code=500))
        self.assertFalse(PushNotificationService.send_to_user(self.user, "T", "M"))
        self.assertTrue(PushSubscription.objects.filter(pk=subscription.pk).exists())

    @patch("notifications.services.push_notification.logger.exception")
    @patch("notifications.services.push_notification.webpush", side_effect=RuntimeError("network"))
    def test_unexpected_error_is_logged_and_does_not_escape(self, _webpush, logger):
        self.subscription()
        self.assertFalse(PushNotificationService.send_to_user(self.user, "T", "M"))
        logger.assert_called_once()

    def test_error_without_response_is_logged_not_deleted(self):
        subscription = self.subscription()
        with patch("notifications.services.push_notification.logger.error") as logger:
            PushNotificationService._handle_error(subscription, WebPushException("failure"))
        self.assertTrue(PushSubscription.objects.filter(pk=subscription.pk).exists())
        logger.assert_called_once()
