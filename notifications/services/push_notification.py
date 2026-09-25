import json
import logging

from django.conf import settings

from pywebpush import webpush, WebPushException

from notifications.models import PushSubscription


logger = logging.getLogger(__name__)


class PushNotificationService:


    @staticmethod
    def send_to_user(
        user,
        title,
        message,
        url="/",
        tag=None,
    ):

        subscriptions = PushSubscription.objects.filter(
            user=user
        )

        if not subscriptions.exists():
            return False

        payload = json.dumps({
            "title": title,
            "message": message,
            "url": url,
            "tag": tag,
        })

        sent = False

        for subscription in subscriptions:

            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": {
                    "p256dh": subscription.p256dh,
                    "auth": subscription.auth,
                }
            }

            try:

                webpush(
                    subscription_info=subscription_info,
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={
                        **settings.VAPID_CLAIMS
                    },
                    ttl=60 * 60,
                    timeout=10,
                )

                sent = True

            except WebPushException as error:

                PushNotificationService._handle_error(
                    subscription,
                    error
                )

            except Exception:

                logger.exception(
                    "Erro inesperado ao enviar push para usuário %s",
                    user.pk
                )

        return sent


    @staticmethod
    def _handle_error(subscription, error):

        response = getattr(error, "response", None)

        status_code = getattr(
            response,
            "status_code",
            None
        )

        # Subscription não existe mais.
        # Ex.: usuário removeu permissão,
        # navegador invalidou o endpoint etc.
        if status_code in [404, 410]:

            subscription.delete()

            logger.info(
                "Push subscription removida por estar inválida."
            )

            return

        logger.error(
            "Erro ao enviar Web Push. Status: %s - %s",
            status_code,
            error
        )