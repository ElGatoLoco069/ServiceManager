import json
from datetime import date, datetime, time, timedelta
from unittest.mock import Mock, patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from app.tests.helpers import make_request, make_service_item, make_service_request, make_service_type, make_user
from diary.services.diary_service import DiaryService
from service_request.models import ServiceRequest, ServiceRequestItem


class DiaryServiceUnitTests(TestCase):
    def setUp(self):
        self.manager = make_user("diary-manager")
        self.operator = make_user("diary-operator", profile_type=Profile.ProfileType.OPERATOR)
        self.service_type = make_service_type(self.manager, "Vistoria")
        self.service_request = make_service_request(self.manager, "DIARY-1")
        self.item = make_service_item(self.manager, self.service_request, self.service_type)

    def test_redirect_name(self):
        self.assertEqual(DiaryService.redirect_name(make_request(data={"return_to": "home"})), "home")
        self.assertEqual(DiaryService.redirect_name(make_request(data={"return_to": "other"})), "view_diary")

    def test_operator_lookup_accepts_pk_or_username(self):
        self.assertIsNone(DiaryService.get_operator(None))
        self.assertEqual(DiaryService.get_operator(str(self.operator.pk)), self.operator)
        self.assertEqual(DiaryService.get_operator(self.operator.username), self.operator)
        self.assertIsNone(DiaryService.get_operator("missing"))
        self.assertIsNone(DiaryService.get_operator("999999"))

    def test_schedule_items_parsing(self):
        payload = [["item", "2026-09-26", "09:00", "scheduled", "operator"]]
        request = make_request(data={"schedule_items": json.dumps(payload)})
        self.assertEqual(DiaryService.get_schedule_items(request), payload)
        with self.assertRaisesMessage(ValueError, "Nenhum item"):
            DiaryService.get_schedule_items(make_request(data={"schedule_items": "[]"}))
        with self.assertRaises(json.JSONDecodeError):
            DiaryService.get_schedule_items(make_request(data={"schedule_items": "{"}))

    def test_scheduled_datetime_is_timezone_aware(self):
        value = DiaryService.get_scheduled_for("2026-09-26", "09:30")
        self.assertTrue(timezone.is_aware(value))
        self.assertEqual(timezone.localtime(value).date(), date(2026, 9, 26))
        self.assertEqual(timezone.localtime(value).time().replace(tzinfo=None), time(9, 30))

    def test_item_validation_covers_cancel_partial_dates_and_operator(self):
        self.assertIsNone(DiaryService.validate_item(self.item, "", "", "canceled", ""))
        self.assertIsNone(DiaryService.validate_item(self.item, "", "", "pending", ""))
        with self.assertRaisesMessage(ValueError, "horário"):
            DiaryService.validate_item(self.item, "2026-09-26", "", "scheduled", self.operator.pk)
        with self.assertRaisesMessage(ValueError, "data"):
            DiaryService.validate_item(self.item, "", "09:00", "scheduled", self.operator.pk)
        with self.assertRaisesMessage(ValueError, "operador responsável"):
            DiaryService.validate_item(self.item, "2026-09-26", "09:00", "scheduled", "")
        with self.assertRaisesMessage(ValueError, "não encontrado"):
            DiaryService.validate_item(self.item, "2026-09-26", "09:00", "scheduled", "missing")
        self.assertEqual(DiaryService.validate_item(self.item, "2026-09-26", "09:00", "scheduled", self.operator.pk), self.operator)

    @patch("diary.services.diary_service.PushNotificationService.send_to_user")
    def test_notify_new_assignment_runs_only_after_commit(self, send):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            DiaryService.notify_new_assignment(self.item, self.operator)
        self.assertEqual(len(callbacks), 1)
        send.assert_called_once_with(
            user=self.operator,
            title="Nova tarefa atribuída",
            message=f"Você recebeu uma nova tarefa: {self.item.service}.",
            url="/operator/list_task/",
            tag=f"service-{self.item.public_id}",
        )

    def test_cancel_item_clears_assignment_and_schedule(self):
        self.item.operator = self.operator
        self.item.scheduled_for = timezone.now()
        self.item.save()
        DiaryService.cancel_item(self.item, self.manager)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.CANCELED)
        self.assertIsNone(self.item.operator)
        self.assertIsNone(self.item.scheduled_for)
        self.assertEqual(self.item.updated_by, self.manager)

    @patch.object(DiaryService, "notify_new_assignment")
    def test_schedule_item_persists_and_notifies_only_for_new_operator(self, notify):
        DiaryService.schedule_item(self.item, self.operator, "2026-09-26", "10:00", self.manager)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.SCHEDULED)
        self.assertEqual(self.item.operator, self.operator)
        notify.assert_called_once_with(self.item, self.operator)

        notify.reset_mock()
        DiaryService.schedule_item(self.item, self.operator, "2026-09-27", "11:00", self.manager)
        notify.assert_not_called()

    def test_request_status_waits_for_pending_then_tracks_scheduled_or_requested(self):
        DiaryService.update_request_status(self.service_request)
        self.service_request.refresh_from_db()
        self.assertEqual(self.service_request.status, ServiceRequest.Status.REQUESTED)

        self.item.status = ServiceRequestItem.Status.SCHEDULED
        self.item.save()
        DiaryService.update_request_status(self.service_request)
        self.service_request.refresh_from_db()
        self.assertEqual(self.service_request.status, ServiceRequest.Status.SCHEDULED)

        with patch.object(ServiceRequest, "save") as save:
            DiaryService.update_request_status(self.service_request)
            save.assert_not_called()

        self.item.status = ServiceRequestItem.Status.CANCELED
        self.item.save()
        DiaryService.update_request_status(self.service_request)
        self.service_request.refresh_from_db()
        self.assertEqual(self.service_request.status, ServiceRequest.Status.REQUESTED)


class DiarySchedulingWorkflowTests(TestCase):
    def setUp(self):
        self.manager = make_user("schedule-manager")
        self.operator = make_user("schedule-operator", profile_type=Profile.ProfileType.OPERATOR)
        self.service_type = make_service_type(self.manager, "Poda")
        self.service_request = make_service_request(self.manager, "SCHEDULE-1")
        self.item = make_service_item(self.manager, self.service_request, self.service_type)

    def schedule(self, payload, return_to="home", request_id=None):
        request = make_request(
            data={"schedule_items": payload if isinstance(payload, str) else json.dumps(payload), "return_to": return_to},
            user=self.manager,
        )
        return DiaryService.to_schedule(request, request_id or self.service_request.public_id), request

    @patch("diary.services.diary_service.PushNotificationService.send_to_user")
    def test_schedule_and_cancel_workflows(self, _send):
        tomorrow = timezone.localdate() + timedelta(days=1)
        response, _ = self.schedule([[str(self.item.public_id), tomorrow.isoformat(), "09:30", "scheduled", str(self.operator.pk)]])
        self.assertEqual(response.url, reverse("home"))
        self.item.refresh_from_db()
        self.service_request.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.SCHEDULED)
        self.assertEqual(self.item.operator, self.operator)
        self.assertEqual(self.service_request.status, ServiceRequest.Status.SCHEDULED)

        response, _ = self.schedule([[str(self.item.public_id), "", "", "canceled", ""]], return_to="diary")
        self.assertEqual(response.url, reverse("view_diary"))
        self.item.refresh_from_db()
        self.service_request.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.CANCELED)
        self.assertEqual(self.service_request.status, ServiceRequest.Status.REQUESTED)

    def test_invalid_inputs_are_rejected_without_mutation(self):
        invalid_payloads = [
            "{",
            [],
            [["too", "short"]],
            [["00000000-0000-0000-0000-000000000001", "", "", "pending", ""]],
            [[str(self.item.public_id), "", "09:00", "scheduled", str(self.operator.pk)]],
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response, request = self.schedule(payload)
                self.assertEqual(response.url, reverse("home"))
                self.item.refresh_from_db()
                self.assertEqual(self.item.status, ServiceRequestItem.Status.PENDING)
                self.assertTrue(list(get_messages(request)))

        response, _ = self.schedule([[str(self.item.public_id), "", "", "pending", ""]], request_id="00000000-0000-0000-0000-000000000001")
        self.assertEqual(response.url, reverse("home"))

    def test_atomic_transaction_rolls_back_earlier_items_on_later_error(self):
        second = make_service_item(self.manager, self.service_request, self.service_type, service="Second")
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        payload = [
            [str(self.item.public_id), tomorrow, "09:00", "scheduled", str(self.operator.pk)],
            [str(second.public_id), "", "10:00", "scheduled", str(self.operator.pk)],
        ]
        self.schedule(payload)
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, ServiceRequestItem.Status.PENDING)

    @patch.object(DiaryService, "get_schedule_items", side_effect=RuntimeError("unexpected"))
    def test_unexpected_error_is_converted_to_message_and_redirect(self, _items):
        response, request = self.schedule([])
        self.assertEqual(response.url, reverse("home"))
        self.assertIn("Erro ao agendar serviços", str(list(get_messages(request))[0]))
