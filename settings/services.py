from settings.models import DomainSetting


class DomainService:

    @staticmethod
    def read_connection():

        connection = DomainSetting.objects.filter(is_active=True).first()

        return connection






