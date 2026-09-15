from service_request.models import ServiceRequest

class DashboardService:

    def get_context():

        context = {
            "awaiting_service_request":ServiceRequest.objects.filter(
                status=ServiceRequest.Status.REQUESTED
            ),
        }

        return context



