import json

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from notifications.models import PushSubscription


class VapidPublicKeyView(LoginRequiredMixin, View):
    login_url = "/accounts/auth/"

    def get(self, request):
        if not settings.VAPID_PUBLIC_KEY:
            return JsonResponse(
                {"error": "Chave VAPID pública não configurada."},
                status=503,
            )

        return JsonResponse({
            "public_key": settings.VAPID_PUBLIC_KEY,
        })


class PushSubscriptionView(LoginRequiredMixin, View):
    login_url = "/accounts/auth/"

    def post(self, request):
        try:
            payload = json.loads(request.body or "{}")

            endpoint = payload.get("endpoint")
            keys = payload.get("keys") or {}
            p256dh = keys.get("p256dh")
            auth = keys.get("auth")

            if not all([
                isinstance(endpoint, str) and endpoint.strip(),
                isinstance(p256dh, str) and p256dh.strip(),
                isinstance(auth, str) and auth.strip(),
            ]):
                return JsonResponse(
                    {"error": "Assinatura push inválida."},
                    status=400,
                )

            subscription, created = (
                PushSubscription.objects.update_or_create(
                    endpoint=endpoint,
                    defaults={
                        "user": request.user,
                        "p256dh": p256dh,
                        "auth": auth,
                    },
                )
            )

            return JsonResponse(
                {
                    "success": True,
                    "created": created,
                    "subscription_id": subscription.pk,
                },
                status=201 if created else 200,
            )

        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse(
                {"error": "JSON inválido."},
                status=400,
            )

    def delete(self, request):
        try:
            payload = json.loads(request.body or "{}")
            endpoint = payload.get("endpoint")

            if not endpoint:
                return JsonResponse(
                    {"error": "Endpoint não informado."},
                    status=400,
                )

            deleted, _ = PushSubscription.objects.filter(
                user=request.user,
                endpoint=endpoint,
            ).delete()

            return JsonResponse({
                "success": True,
                "deleted": bool(deleted),
            })

        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse(
                {"error": "JSON inválido."},
                status=400,
            )