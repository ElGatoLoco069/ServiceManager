
from django.contrib import messages

from registers.models import ServiceType
from django.shortcuts import redirect


class RegisterService:


    def get_service_type():

        return ServiceType.objects.all()


    def read_form(request):

        context = {
            "name":request.POST.get("name"),
            "default_unit":request.POST.get("default_unit"),
            "is_active":request.POST.get("is_active"),
        }

        return context


    def verify_form(request, context, service=None):

        errors = []
        valid_values = {"False", "True"}

        try:

            if service is None:

                if not (context.get("name") or "").strip():
                    errors.append("É necessario informar o nome do serviço!")

                if ServiceType.objects.filter(name__iexact=context["name"]):
                    errors.append("Serviço já cadastrado!")

                if context['is_active'] == "False":
                    errors.append("É necessario definir o status como ativo!")

            else:

                if ServiceType.objects.filter(name=context["name"]).exclude(public_id=service.public_id).exists():
                    errors.append("Serviço já cadastrado!")


            if context['default_unit'] is None or context['default_unit'] == "" or context['default_unit'] == " ":
                errors.append("É necessario informar a unidade de medida!")


            if context['is_active'] not in valid_values:
                errors.append("É necessario informar se é Ativo ou Inativo!")

            return errors

        except Exception as e:
            messages.error(request, f"Erro ao validar campos do formulario! Erro {e}")
            return redirect("list_services")


    def save_service_type(request):

        context = RegisterService.read_form(request)
        errors = RegisterService.verify_form(request, context)

        if errors:
            for error in errors:
                messages.warning(request, error)
                return redirect("list_services")

        try:

            ServiceType.objects.create(
                name=context['name'],
                default_unit=context['default_unit'],
                is_active=context['is_active'],
                created_by=request.user,
                updated_by=request.user,
            )

            messages.success(request, f"Serviço {context['name']} cadastrado com sucesso!")
            return redirect("list_services")

        except Exception as e:
            messages.error(request, f"Erro ao salvar novo serviço! Erro: {e}")
            return redirect("list_services")
                

    def update_service_type(request, service):

        context = RegisterService.read_form(request)
        service_db = ServiceType.objects.filter(public_id=service).first()
        errors = RegisterService.verify_form(request, context, service_db)

        if errors:
            for error in errors:
                messages.warning(request, error)
                return redirect("list_services")

        try:

            service_db.name=context['name']
            service_db.default_unit=context['default_unit']

            if service_db.is_active:
                service_db.is_active=False
            else:
                service_db.is_active=True

            service_db.updated_by=request.user

            service_db.save()

            messages.success(request, f"Serviço {context['name']} atualizado com sucesso!")
            return redirect("list_services")

        except Exception as e:
            messages.error(request, f"Erro ao atualizar serviço! Erro: {e}")
            return redirect("list_services")