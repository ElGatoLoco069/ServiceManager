from django.contrib import messages
from django.shortcuts import redirect, render
from service_request.models import ServiceRequest, ServiceRequestItem

@staticmethod
def read_form(request):

    try:

        context = {
            'protocol':request.GET.get("protocol"),
            'verify_code':request.GET.get("verify_code"),
        }

        return context

    except Exception as e:
        messages.error(request, f"Erro ao tentar fazer a leitura do formulario! Erro: {e}")
        return redirect("consult_protocol")


@staticmethod
def verify_form(request, context):

    try:

        errors = []

        if not (context.get("protocol") or "").strip():
            errors.append("É necessario informar o numero do protocolo!")

        if not (context.get("verify_code") or "").strip():
            errors.append("É necessario informar os 4 primeiros digitos do CPF/CNPJ!")

        return errors

    except Exception as e:
        messages.error(request, f"Erro ao validar formulario! Erro {e}")
        return redirect("consult_protocol")


@staticmethod
def search_protocol(request):

    try:

        context = read_form(request)
        errors = verify_form(request, context)

        if errors:
            for error in errors:
                messages.warning(request, error)
                return redirect("consult_protocol")

        protocol = ServiceRequest.objects.filter(protocol=context['protocol'], requester_document__icontains=context['verify_code']).first()

        if not protocol:
            messages.warning(request, f"Nenhum protocolo de serviço encontrado!")
            return redirect("consult_protocol")

        protocol_itens = ServiceRequestItem.objects.filter(service_request=protocol)

        if not protocol_itens:
            messages.warning(request, f"Nenhum serviço encontrado para o protocolo {protocol.protocol}!")
            return redirect("consult_protocol")

        

        context = {
            'protocol':protocol,
            'protocol_itens':protocol_itens,
        }

        return render(request, "protocol_detail.html", {"context":context})

    except Exception as e:
        messages.error(request, f"Erro ao tentar procurar o protocolo! Erro: {e}")
        print(e)
        return redirect("consult_protocol")
        


