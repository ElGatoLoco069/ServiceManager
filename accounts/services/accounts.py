import logging
import re
from typing import Any
import ssl
from dotenv import load_dotenv
from pathlib import Path
import os

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.utils.http import url_has_allowed_host_and_scheme

from ldap3 import Connection, NONE, Server, SUBTREE, Tls, FIRST, ServerPool
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from settings.services import DomainService


logger = logging.getLogger(__name__)
User = get_user_model()


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

class AuthenticationService:

    """
    Serviço responsável por:

    - Ler e validar o formulário de autenticação;
    - Autenticar o usuário no Active Directory;
    - Identificar problemas na conta do AD;
    - Sincronizar os dados do usuário com o Django;
    - Iniciar a sessão do usuário no sistema.
    """

    AD_AUTH_MESSAGES = {
        "52e": "Usuário ou senha inválidos.",
        "530": "O acesso à sua conta não é permitido neste horário.",
        "531": (
            "O acesso à sua conta não é permitido a partir deste computador."
        ),
        "532": (
            "Sua senha expirou e precisa ser alterada. "
            "Altere sua senha em um computador conectado ao domínio."
        ),
        "533": (
            "Sua conta está desativada. "
            "Entre em contato com a equipe de TI."
        ),
        "701": (
            "Sua conta expirou. "
            "Entre em contato com a equipe de TI."
        ),
        "773": (
            "Você precisa alterar sua senha antes de acessar o sistema. "
            "Faça a alteração em um computador conectado ao domínio."
        ),
        "775": (
            "Sua conta está bloqueada. "
            "Aguarde o desbloqueio automático ou entre em contato com a equipe de TI."
        ),
    }

    DEFAULT_AUTH_ERROR_MESSAGE = (
        "Não foi possível realizar a autenticação. "
        "Verifique seus dados e tente novamente."
    )

    LDAP_CONNECTION_ERROR_MESSAGE = (
        "Não foi possível se comunicar com o servidor de autenticação. "
        "Tente novamente mais tarde."
    )


    @staticmethod
    def read_form(request) -> dict[str, str]:
        """
        Lê os campos enviados pelo formulário de login.
        """

        return {
            "username": request.POST.get("username", "").strip(),
            "password": request.POST.get("password", ""),
        }


    @staticmethod
    def form_validate(form: dict[str, str]) -> list[str]:
        """
        Valida os campos obrigatórios do formulário.
        """

        errors: list[str] = []

        if not form.get("username", "").strip():
            errors.append("Informe um usuário válido.")

        if not form.get("password", "").strip():
            errors.append("Informe uma senha válida.")

        return errors


    @staticmethod
    def authenticate(request):
        """
        Executa o fluxo completo de autenticação.
        """

        form = AuthenticationService.read_form(request)
        errors = AuthenticationService.form_validate(form)

        if errors:
            messages.warning(request, errors[0])
            return redirect("auth")

        auth_result = AuthenticationService.authenticate_ad(
            username=form["username"],
            password=form["password"],
        )

        if not auth_result["success"]:
            messages.error(
                request,
                auth_result["message"],
            )
            return redirect("auth")

        ad_user = auth_result["user"]

        if not ad_user:
            messages.error(
                request,
                AuthenticationService.DEFAULT_AUTH_ERROR_MESSAGE,
            )
            return redirect("auth")

        user, created = User.objects.get_or_create(
            username=form["username"],
        )

        user.first_name = ad_user["first_name"]
        user.last_name = ad_user["last_name"]
        user.email = ad_user["email"]

        if created:
            user.set_unusable_password()

        if created:
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "email",
                    "password",
                ]
            )
        else:
            user.save(
                update_fields=[
                    "first_name",
                    "last_name",
                    "email",
                ]
            )

        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )

        messages.success(
            request,
            f"Bem-vindo, {user.get_full_name()}!",
        )

        allowed_hosts = {request.get_host()}
        next_url = request.POST.get('next')

        is_safe = url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts=allowed_hosts,
            require_https=request.is_secure()
        )

        if is_safe:
            return redirect(next_url)

        return redirect("home")


    @staticmethod
    def authenticate_ad(username: str, password: str,) -> dict[str, Any]:
        domain_settings = DomainService.read_connection()
        """
        Autentica o usuário no Active Directory.

        Retorna um dicionário contendo:

        - success: indica se a autenticação foi bem-sucedida;
        - message: mensagem que poderá ser apresentada ao usuário;
        - code: código retornado pelo Active Directory;
        - user: dados do usuário autenticado.
        """

        try:

            tls_config = Tls(
                validate=ssl.CERT_REQUIRED,
                ca_certs_file=os.getenv('CERTIFICATE'),
            )

            ldap_host = os.getenv('DOMAIN_CONTROL')
            ldap_host02 = os.getenv('DOMAIN_CONTROL02')

            dc01 = Server(
                host=ldap_host,
                port=636,
                use_ssl=True,
                tls=tls_config,
                get_info=NONE,
                connect_timeout=3,
            )

            dc02 = Server(
                host=ldap_host02,
                port=636,
                use_ssl=True,
                tls=tls_config,
                get_info=NONE,
                connect_timeout=3,
            )

            server_pool = ServerPool(
                [dc01, dc02],
                pool_strategy=FIRST,
                active=True,
                exhaust=True,
            )
            
            bind_user = f"{username}@{domain_settings.domain_name}"

            conn = Connection(
                server=server_pool,
                user=bind_user,
                password=password,
                receive_timeout=5,
                auto_bind=False,
                raise_exceptions=False,
            )

            try:
                if not conn.bind():
                    error_code = AuthenticationService.get_ad_error_code(
                        conn.result
                    )

                    error_message = (
                        AuthenticationService.AD_AUTH_MESSAGES.get(
                            error_code,
                            AuthenticationService.DEFAULT_AUTH_ERROR_MESSAGE,
                        )
                    )

                    logger.warning(
                        (
                            "Falha no login LDAP. "
                            "Usuário=%s, código=%s, descrição=%s"
                        ),
                        username,
                        error_code,
                        conn.result.get("description"),
                    )

                    return {
                        "success": False,
                        "message": error_message,
                        "code": error_code,
                        "user": None,
                    }

                ad_user = AuthenticationService.get_ad_user_data(
                    conn=conn,
                    username=username,
                    domain_name=domain_settings.domain_name,
                    search_base=domain_settings.search_base,
                )

                return {
                    "success": True,
                    "message": "",
                    "code": None,
                    "user": ad_user,
                }

            finally:
                if conn.bound:
                    conn.unbind()

        except LDAPException:
            logger.exception(
                "Erro LDAP ao autenticar o usuário %s.",
                username,
            )

            return {
                "success": False,
                "message": (
                    AuthenticationService.LDAP_CONNECTION_ERROR_MESSAGE
                ),
                "code": "ldap_error",
                "user": None,
            }

        except (AttributeError, TypeError, ValueError):
            logger.exception(
                "Configuração inválida do domínio durante o login de %s.",
                username,
            )

            return {
                "success": False,
                "message": (
                    "O serviço de autenticação está configurado "
                    "incorretamente. Entre em contato com a equipe de TI."
                ),
                "code": "configuration_error",
                "user": None,
            }

        except Exception:
            logger.exception(
                "Erro inesperado durante a autenticação do usuário %s.",
                username,
            )

            return {
                "success": False,
                "message": (
                    AuthenticationService.LDAP_CONNECTION_ERROR_MESSAGE
                ),
                "code": "unexpected_error",
                "user": None,
            }


    @staticmethod
    def get_ad_error_code(result: dict | None) -> str | None:
        """
        Extrai o código de erro retornado pelo Active Directory.

        Exemplo de mensagem recebida:

        AcceptSecurityContext error, data 533, v...
        """

        if not result:
            return None

        message = str(result.get("message", "")).lower()

        match = re.search(
            r"\bdata\s+([0-9a-f]+)\b",
            message,
        )

        if not match:
            return None

        return match.group(1).lower()


    @staticmethod
    def get_ad_user_data(conn: Connection, username: str, domain_name: str, search_base: str,) -> dict[str, str]:
        """
        Consulta os dados do usuário autenticado no Active Directory.
        """

        safe_username = escape_filter_chars(username)

        safe_user_principal_name = escape_filter_chars(
            f"{username}@{domain_name}"
        )

        search_filter = (
            "(|"
            f"(sAMAccountName={safe_username})"
            f"(userPrincipalName={safe_user_principal_name})"
            ")"
        )

        search_success = conn.search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=[
                "displayName",
                "givenName",
                "sn",
                "mail",
            ],
            size_limit=1,
        )

        if not search_success:
            logger.warning(
                "A busca LDAP falhou para o usuário %s. Resultado=%s",
                username,
                conn.result,
            )

        if not conn.entries:
            logger.warning(
                (
                    "O usuário %s foi autenticado, mas seus dados "
                    "não foram localizados na pesquisa LDAP."
                ),
                username,
            )

            return {
                "first_name": username,
                "last_name": "",
                "email": "",
            }

        entry = conn.entries[0]

        display_name = AuthenticationService.get_ad_attr(
            entry,
            "displayName",
        )

        first_name = AuthenticationService.get_ad_attr(
            entry,
            "givenName",
        )

        last_name = AuthenticationService.get_ad_attr(
            entry,
            "sn",
        )

        email = AuthenticationService.get_ad_attr(
            entry,
            "mail",
        )

        if display_name and not first_name:
            name_parts = display_name.split(maxsplit=1)

            first_name = name_parts[0]

            if len(name_parts) > 1 and not last_name:
                last_name = name_parts[1]

        return {
            "first_name": first_name or display_name or username,
            "last_name": last_name or "",
            "email": email or "",
        }


    @staticmethod
    def get_ad_attr(entry, attribute_name: str,) -> str:

        attribute = getattr(
            entry,
            attribute_name,
            None,
        )

        if attribute is None:
            return ""

        value = attribute.value

        if value is None:
            return ""

        return str(value).strip()
    

    @login_required
    @require_POST
    @staticmethod
    def logout_service(request):
        logout(request)

        messages.success(
            request,
            "Logout efetuado com sucesso! Até mais 👋",
        )

        return redirect("auth")


