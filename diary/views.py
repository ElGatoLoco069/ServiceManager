from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View

@method_decorator(login_required(login_url="/accounts/auth/"), name="dispatch")
class DiaryView(View):

    def get(self, request):

        return render(request, "diary.html")
