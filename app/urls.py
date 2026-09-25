"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from accounts.views import AuthenticationView, logout_view, UserProfileView
from dashboard.views import HomeView

from registers.views import ListServiceTypeView, CreateServiceTypeView, UpdateServiceTypeView
from diary.views import DiaryView, ScheduleServiceItemView
from service_request.views import CreateServiceRequestView, ServiceRequestFormView, SearchProtocolView, ProtocolDetailView, view_protocol_attachment

from field_operator.views import OperatorView, StartServiceView, FinishServiceView
from notifications.views import VapidPublicKeyView, PushSubscriptionView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', AuthenticationView.as_view(), name="auth_clean"),
    path('accounts/auth/', AuthenticationView.as_view(), name='auth'),
    path('accounts/logout/', logout_view.as_view(), name='logout'),
    path("accounts/user_profile/", UserProfileView.as_view(), name="user_profile"),

    path("dashboard/home/", HomeView.as_view(), name="home"),

    path("registers/list_services/", ListServiceTypeView.as_view(), name="list_services"),
    path("registers/create_service/", CreateServiceTypeView.as_view(), name=("create_service")),
    path("registers/update_service/<str:uuid>/", UpdateServiceTypeView.as_view(), name="update_service"),

    path("diary/view/", DiaryView.as_view(), name="view_diary"),
    path("diary/request_service/schedule/<str:service_request_id>/", ScheduleServiceItemView.as_view(), name="schedule_request_service"),
    path("service_request/service_request_form/", ServiceRequestFormView.as_view(), name="service_request_form"),
    path("service_request/create_service_request/", CreateServiceRequestView.as_view(), name="create_service_request"),

    path("protocol/consult_protocol/", SearchProtocolView.as_view(), name="consult_protocol"),
    path("protocol/protocol_detail/", ProtocolDetailView.as_view(), name="protocol_detail"),
    path("protocol/view_protocol_attachment/<uuid:attachment_id>/", view_protocol_attachment, name="view_protocol_attachment",),

    path("operator/list_task/", OperatorView.as_view(), name="list_task"),
    path("opertor/start_task/<str:service_id>/", StartServiceView.as_view(), name="start_task"),
    path("opertor/finish_task/<str:service_id>/", FinishServiceView.as_view(), name="finish_task"),

    path("vapid-public-key/", VapidPublicKeyView.as_view(), name="vapid_public_key",),
    path("subscription/", PushSubscriptionView.as_view(), name="subscription",),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)