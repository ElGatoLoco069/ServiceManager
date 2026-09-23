import mimetypes
import os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

import django

django.setup()

from django.contrib.messages.storage.fallback import FallbackStorage
from django.template.loader import render_to_string
from django.test import RequestFactory


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "app" / "static"


class Items:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values


def build_page():
    factory = RequestFactory()
    request = factory.get("/diary/view/")
    request.session = {}
    request._messages = FallbackStorage(request)
    request.resolver_match = SimpleNamespace(url_name="view_diary")
    request.user = SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        first_name="Gestor",
        last_name="Teste",
        username="gestor.teste",
        profile=SimpleNamespace(profile_type="manager"),
        get_full_name=lambda: "Gestor Teste",
    )

    items = Items([
        SimpleNamespace(
            public_id="00000000-0000-0000-0000-000000000101",
            service="Nivelamento de terreno",
            amount=5,
            unit="horas",
            scheduled_for=None,
            status="pending",
        ),
        SimpleNamespace(
            public_id="00000000-0000-0000-0000-000000000102",
            service="Entrega de terra",
            amount=3,
            unit="cargas",
            scheduled_for=None,
            status="pending",
        ),
    ])
    service_request = SimpleNamespace(
        public_id="00000000-0000-0000-0000-000000000001",
        protocol="SRV-2026-0101",
        requester_name="Solicitante de teste",
        created_at=datetime(2026, 9, 23, 10, 30),
        items=items,
    )
    operators = [
        SimpleNamespace(user=SimpleNamespace(pk=101, username="ana.souza", get_full_name=lambda: "Ana Souza")),
        SimpleNamespace(user=SimpleNamespace(pk=102, username="carlos.lima", get_full_name=lambda: "Carlos Lima")),
    ]
    context = {
        "context": {
            "get_awaiting_service_request": [service_request],
            "get_all": [],
            "services": [SimpleNamespace(name="Nivelamento de terreno", is_active=True)],
            "operators": operators,
        }
    }
    return render_to_string("diary.html", context, request=request).encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/diary/view/":
            body = build_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path.startswith("/static/"):
            relative = self.path.removeprefix("/static/").split("?", 1)[0]
            path = (STATIC_ROOT / relative).resolve()
            if STATIC_ROOT.resolve() in path.parents and path.is_file():
                body = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

        self.send_error(404)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8003), Handler).serve_forever()
