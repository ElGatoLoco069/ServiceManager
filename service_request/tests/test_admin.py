from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib import admin
from django.test import TestCase

from app.tests.helpers import make_service_item, make_service_request, make_service_type, make_user
from service_request.admin import ServiceRequestAdmin, ServiceRequestItemAdmin, ServiceRequestItemPhotoAdmin
from service_request.models import ServiceRequest, ServiceRequestItem, ServiceRequestItemPhoto


class ServiceRequestAdminTests(TestCase):
    def setUp(self):
        self.actor = make_user("request-admin", is_superuser=True)
        self.service_type = make_service_type(self.actor)

    def test_request_and_item_save_model_populate_audit_fields(self):
        request = Mock(user=self.actor)
        unsaved_request = ServiceRequest(protocol="ADMIN-1", requester_name="A", requester_phone="1", service_address="A", service_neighborhood="N")
        request_admin = ServiceRequestAdmin(ServiceRequest, admin.site)
        with patch("django.contrib.admin.ModelAdmin.save_model") as parent:
            request_admin.save_model(request, unsaved_request, Mock(), False)
            self.assertEqual(unsaved_request.created_by, self.actor)
            self.assertEqual(unsaved_request.updated_by, self.actor)
            parent.assert_called_once()

        persisted_request = make_service_request(self.actor, "ADMIN-2")
        unsaved_item = ServiceRequestItem(service_request=persisted_request, service_id=self.service_type, service="X")
        item_admin = ServiceRequestItemAdmin(ServiceRequestItem, admin.site)
        with patch("django.contrib.admin.ModelAdmin.save_model"):
            item_admin.save_model(request, unsaved_item, Mock(), False)
        self.assertEqual(unsaved_item.created_by, self.actor)
        self.assertEqual(unsaved_item.updated_by, self.actor)

        existing_item = make_service_item(self.actor, persisted_request, self.service_type)
        original_creator = existing_item.created_by
        with patch("django.contrib.admin.ModelAdmin.save_model"):
            item_admin.save_model(request, existing_item, Mock(), True)
        self.assertEqual(existing_item.created_by, original_creator)
        self.assertEqual(existing_item.updated_by, self.actor)

    def test_request_admin_preserves_creator_on_existing_objects(self):
        creator = make_user("original-creator")
        service_request = make_service_request(creator, "ADMIN-EXISTING")
        request_admin = ServiceRequestAdmin(ServiceRequest, admin.site)
        with patch("django.contrib.admin.ModelAdmin.save_model"):
            request_admin.save_model(Mock(user=self.actor), service_request, Mock(), True)
        self.assertEqual(service_request.created_by, creator)
        self.assertEqual(service_request.updated_by, self.actor)

    def test_save_formset_sets_audit_saves_deletes_and_m2m(self):
        service_request = make_service_request(self.actor, "FORMSET")
        item = ServiceRequestItem(service_request=service_request, service_id=self.service_type, service="Unsaved")
        existing_item = make_service_item(self.actor, service_request, self.service_type, service="Existing")
        existing_creator = existing_item.created_by
        unrelated = Mock()
        deleted = Mock()
        formset = Mock()
        formset.save.return_value = [item, existing_item, unrelated]
        formset.deleted_objects = [deleted]
        model_admin = ServiceRequestAdmin(ServiceRequest, admin.site)

        model_admin.save_formset(Mock(user=self.actor), Mock(), formset, False)
        self.assertEqual(item.created_by, self.actor)
        self.assertEqual(item.updated_by, self.actor)
        self.assertIsNotNone(item.pk)
        existing_item.refresh_from_db()
        self.assertEqual(existing_item.created_by, existing_creator)
        self.assertEqual(existing_item.updated_by, self.actor)
        unrelated.save.assert_called_once()
        deleted.delete.assert_called_once()
        formset.save_m2m.assert_called_once()

    def test_photo_previews_cover_empty_thumbnail_and_large_link(self):
        photo_admin = ServiceRequestItemPhotoAdmin(ServiceRequestItemPhoto, admin.site)
        empty = SimpleNamespace(image=None)
        self.assertEqual(photo_admin.image_preview(empty), "-")
        self.assertEqual(photo_admin.image_preview_large(empty), "Nenhuma imagem enviada.")

        image = SimpleNamespace(url="/media/photo.jpg")
        obj = SimpleNamespace(image=image)
        self.assertIn("<img", str(photo_admin.image_preview(obj)))
        self.assertIn('href="/media/photo.jpg"', str(photo_admin.image_preview_large(obj)))
