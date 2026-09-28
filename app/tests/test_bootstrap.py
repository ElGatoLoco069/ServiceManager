import importlib
import os
import runpy
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import clear_url_caches


class DjangoBootstrapTests(SimpleTestCase):
    def test_wsgi_asgi_and_empty_settings_view_module_import(self):
        asgi = importlib.import_module("app.asgi")
        wsgi = importlib.import_module("app.wsgi")
        settings_views = importlib.import_module("settings.views")
        self.assertIsNotNone(asgi.application)
        self.assertIsNotNone(wsgi.application)
        self.assertTrue(hasattr(settings_views, "render"))

    def test_settings_module_can_evaluate_production_branch(self):
        settings_path = Path(__file__).resolve().parents[1] / "settings.py"
        with patch.dict(os.environ, {"SERVER_ENVIRONMENT": "production", "SECRET_KEY": "test"}), patch("dotenv.load_dotenv"):
            namespace = runpy.run_path(str(settings_path), init_globals={"DEBUG": False})
        self.assertFalse(namespace["DEBUG"])
        self.assertTrue(namespace["SESSION_COOKIE_SECURE"])
        self.assertNotIn("DATABASES", namespace)

    def test_debug_url_configuration_adds_media_route(self):
        import app.urls

        with override_settings(DEBUG=True):
            importlib.reload(app.urls)
            self.assertTrue(any("media/" in str(pattern.pattern) for pattern in app.urls.urlpatterns))

        importlib.reload(app.urls)
        clear_url_caches()
