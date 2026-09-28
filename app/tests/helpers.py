from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory

from accounts.models import Profile
from registers.models import ServiceType
from service_request.models import ServiceRequest, ServiceRequestItem


User = get_user_model()


def make_user(
    username="manager",
    *,
    profile_type=Profile.ProfileType.MANAGER,
    password="test-password",
    is_superuser=False,
):
    user = User.objects.create_user(
        username=username,
        password=password,
        is_superuser=is_superuser,
        is_staff=is_superuser,
    )
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.profile_type = profile_type
    profile.created_by = profile.created_by or user
    profile.updated_by = user
    profile.save()
    return user


def make_service_type(user, name="Vistoria", default_unit="unidade", **kwargs):
    return ServiceType.objects.create(
        name=name,
        default_unit=default_unit,
        created_by=user,
        updated_by=user,
        **kwargs,
    )


def make_service_request(user, protocol="SRV-TEST", **kwargs):
    defaults = {
        "requester_name": "Solicitante teste",
        "requester_phone": "45999999999",
        "requester_document": "12345678900",
        "service_address": "Rua de teste",
        "service_neighborhood": "Centro",
        "created_by": user,
        "updated_by": user,
    }
    defaults.update(kwargs)
    return ServiceRequest.objects.create(protocol=protocol, **defaults)


def make_service_item(user, service_request, service_type=None, **kwargs):
    service_type = service_type or make_service_type(user)
    defaults = {
        "service": service_type.name,
        "amount": Decimal("1.00"),
        "unit": service_type.default_unit,
        "created_by": user,
        "updated_by": user,
    }
    defaults.update(kwargs)
    return ServiceRequestItem.objects.create(
        service_request=service_request,
        service_id=service_type,
        **defaults,
    )


def make_request(method="post", path="/", data=None, *, user=None, files=None):
    factory = RequestFactory()
    payload = data or {}
    if method.lower() == "get":
        request = factory.get(path, payload)
    elif method.lower() == "delete":
        request = factory.delete(path, data=payload, content_type="application/json")
    else:
        if files:
            payload = {**payload, **files}
        request = factory.post(path, payload)

    SessionMiddleware(lambda req: None).process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)
    if user is not None:
        request.user = user
    return request


def tiny_upload(name="evidence.jpg", content=b"image-content"):
    return SimpleUploadedFile(name, content, content_type="image/jpeg")
