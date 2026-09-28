from django.test import TestCase

from settings.models import DomainSetting
from settings.services import DomainService


class DomainSettingTests(TestCase):
    def test_string_and_active_connection_lookup(self):
        inactive = DomainSetting.objects.create(domain_name="old.example", search_base="dc=old", is_active=False)
        active = DomainSetting.objects.create(domain_name="example.test", search_base="dc=example,dc=test")
        self.assertEqual(str(active), "example.test")
        self.assertEqual(DomainService.read_connection(), active)
        active.is_active = False
        active.save()
        self.assertIsNone(DomainService.read_connection())
        self.assertEqual(str(inactive), "old.example")

    def test_admin_registration_and_configuration(self):
        from django.contrib import admin
        from settings.admin import DomainSettingAdmin

        self.assertIsInstance(admin.site._registry[DomainSetting], DomainSettingAdmin)
        self.assertIn("domain_name", DomainSettingAdmin.list_display)
        self.assertIn("is_active", DomainSettingAdmin.list_filter)
