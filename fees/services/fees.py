from django.shortcuts import redirect
from django.contrib import messages


@staticmethod
def read_form(request):

    try:

        context = {
            "service":request.POST.get("service"),
            "description":request.POST.get("description"),
            "value":request.POST.get("value"),
            "minimum_base_value":request.POST.get("minimum_base_value"),
            "active":request.POST.get("active"),
        }

        return context

    except Exception as e:
        messages.error(request, f"Erro ao fazer leitura do formulario! Erro: {e}")
        return redirect("list_services")


@staticmethod
def validate_form(request, context):

    try:
    
        errors = []

    




    except Exception as e:
        messages.error(request, f"Erro ao tentar validar formulario! Erro: {e}")
        return redirect("list_services")

    





