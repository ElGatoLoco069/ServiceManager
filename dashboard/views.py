from django.shortcuts import render
from django.views.generic import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

# Create your views here.

@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class HomeView(View):

    def get(self, request):
        return render(request, "home.html",)