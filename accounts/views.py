from django.shortcuts import render
from django.views.generic import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from accounts.services.accounts import AuthenticationService
from accounts.services.profile import get_profile_user, update_profile
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



@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class UserProfileView(View):

    def get(self, request):

        return get_profile_user(request)


@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class UserUpdateProfileView(View):

    def get(self, request):

        return get_profile_user(request)


    def post(self, request):

        return update_profile(request)        