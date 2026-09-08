from django.shortcuts import render, redirect
from django.views.generic import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from accounts.services import AuthenticationService

# Create your views here.

class AuthenticationView(View):

    def get(self, request):

        next_url = request.GET.get('next')

        return render(request, 'login.html', {"next":next_url,})

    
    def post(self, request):

        return AuthenticationService.authenticate(request)


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class logout_view(View):

    def post(self, request):
        return AuthenticationService.logout_service(request)


def page_not_found(request, exception):
    return render(
        request,
        "404_maqflow.html",
        status=404,
    )