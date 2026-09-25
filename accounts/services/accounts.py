import hashlib
import logging
import math
import os
import re
import ssl
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ldap3 import Connection, FIRST, NONE, SUBTREE, Server, ServerPool, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars

from settings.services import DomainService


logger = logging.getLogger(__name__)
User = get_user_model()

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class AuthenticationService:
    """
    Serviço responsável por:

    - Ler e validar o formulário de autenticação;
    - Aplicar rate limit por IP e usuário;
    - Autenticar o usuário no Active Directory;
    - Identificar problemas na conta do AD;
    - Sincronizar os dados do usuário com o Django;
    - Iniciar a sessão do usuário no sistema.
    """

    RATE_LIMIT_WINDOW_SECONDS = 5 * 60
    RATE_LIMIT_IP_MAX_ATTEMPTS = 10
    RATE_LIMIT_USER_MAX_ATTEMPTS = 5

    # Erros de infraestrutura/configuração não devem consumir tentativas
    # de autenticação do usuário.
    RATE_LIMIT_IGNORED_ERROR_CODES = {
        "ldap_error",
        "configuration_error",
        "unexpected_error",
    }

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

    # -------------------------------------------------------------------------
    # FORMULÁRIO
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # RATE LIMIT
    # -------------------------------------------------------------------------

    @staticmethod
    def get_client_ip(request) -> str:
        """
        Obtém o IP utilizado pelo rate limit.

        Por segurança, X-Forwarded-For só é considerado se a aplicação
        declarar explicitamente RATE_LIMIT_TRUST_X_FORWARDED_FOR=True
        no settings.py.

        Não habilite essa opção se o cliente puder acessar o Django
        diretamente, pois o cabeçalho X-Forwarded-For pode ser falsificado.
        """

        trust_forwarded_for = getattr(
            settings,
            "RATE_LIMIT_TRUST_X_FORWARDED_FOR",
            False,
        )

        if trust_forwarded_for:
            forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")

            if forwarded_for:
                client_ip = forwarded_for.split(",", 1)[0].strip()

                if client_ip:
                    return client_ip

        return request.META.get("REMOTE_ADDR") or "unknown"

    @staticmethod
    def normalize_username(username: str) -> str:
        """
        Normaliza o usuário apenas para geração da chave de rate limit.

        O valor original continua sendo utilizado para autenticação no AD.
        """

        return str(username or "").strip().casefold()

    @staticmethod
    def generate_rate_limit_key(prefix: str, value: str) -> str:
        """
        Gera uma chave de cache sem armazenar IP ou username em texto puro.
        """

        normalized_value = str(value or "").strip().casefold()

        digest = hashlib.sha256(
            normalized_value.encode("utf-8")
        ).hexdigest()

        return f"authentication:rate-limit:{prefix}:{digest}"

    @staticmethod
    def get_rate_limit_status(key: str) -> tuple[bool, int]:
        """
        Verifica se a chave está temporariamente bloqueada.

        Retorna:
            (bloqueado, segundos_restantes)
        """

        block_key = f"{key}:blocked_until"
        blocked_until = cache.get(block_key)

        if blocked_until is None:
            return False, 0

        try:
            blocked_until = float(blocked_until)
        except (TypeError, ValueError):
            cache.delete(block_key)
            return False, 0

        remaining_seconds = math.ceil(
            blocked_until - time.time()
        )

        if remaining_seconds <= 0:
            cache.delete(block_key)
            cache.delete(f"{key}:attempts")
            return False, 0

        return True, remaining_seconds

    @staticmethod
    def register_failed_attempt(
        key: str,
        max_attempts: int,
    ) -> tuple[bool, int]:
        """
        Registra uma falha de autenticação.

        O contador existe durante a janela de rate limit.
        Ao atingir o limite, o contador é substituído por um bloqueio
        temporário.

        Retorna:
            (bloqueado, segundos_restantes)
        """

        attempts_key = f"{key}:attempts"
        block_key = f"{key}:blocked_until"

        # Caso já esteja bloqueado, apenas retorna o tempo restante.
        blocked, remaining = AuthenticationService.get_rate_limit_status(
            key
        )

        if blocked:
            return True, remaining

        # cache.add é atômico nos backends mais comuns.
        created = cache.add(
            attempts_key,
            1,
            timeout=AuthenticationService.RATE_LIMIT_WINDOW_SECONDS,
        )

        if created:
            attempts = 1
        else:
            try:
                attempts = cache.incr(attempts_key)
            except (ValueError, NotImplementedError):
                # Fallback para backends sem suporte adequado a incr().
                attempts = int(cache.get(attempts_key, 0)) + 1
                cache.set(
                    attempts_key,
                    attempts,
                    timeout=AuthenticationService.RATE_LIMIT_WINDOW_SECONDS,
                )

        if attempts < max_attempts:
            return False, 0

        blocked_until = (
            time.time()
            + AuthenticationService.RATE_LIMIT_WINDOW_SECONDS
        )

        cache.set(
            block_key,
            blocked_until,
            timeout=AuthenticationService.RATE_LIMIT_WINDOW_SECONDS,
        )

        # Durante o bloqueio não precisamos manter o contador.
        cache.delete(attempts_key)

        return (
            True,
            AuthenticationService.RATE_LIMIT_WINDOW_SECONDS,
        )

    @staticmethod
    def reset_user_rate_limit(username: str) -> None:
        """
        Limpa o contador/bloqueio associado ao usuário após login válido.

        O contador do IP NÃO é resetado, evitando que alguém utilize
        credenciais válidas para zerar a proteção daquele endereço.
        """

        normalized_username = AuthenticationService.normalize_username(
            username
        )

        if not normalized_username:
            return

        user_key = AuthenticationService.generate_rate_limit_key(
            "username",
            normalized_username,
        )

        cache.delete(f"{user_key}:attempts")
        cache.delete(f"{user_key}:blocked_until")

    @staticmethod
    def format_retry_time(seconds: int) -> str:
        """
        Formata o tempo restante de forma amigável.
        """

        seconds = max(1, math.ceil(seconds))

        minutes, remaining_seconds = divmod(seconds, 60)

        parts: list[str] = []

        if minutes:
            minute_label = "minuto" if minutes == 1 else "minutos"
            parts.append(f"{minutes} {minute_label}")

        if remaining_seconds:
            second_label = (
                "segundo"
                if remaining_seconds == 1
                else "segundos"
            )
            parts.append(
                f"{remaining_seconds} {second_label}"
            )

        if not parts:
            return "1 segundo"

        return " e ".join(parts)

    @staticmethod
    def get_rate_limit_message(remaining_seconds: int) -> str:
        """
        Gera uma mensagem genérica.

        Não informa ao cliente se o bloqueio ocorreu por IP ou username.
        """

        retry_time = AuthenticationService.format_retry_time(
            remaining_seconds
        )

        return (
            "Muitas tentativas de login foram realizadas. "
            f"Tente novamente em {retry_time}."
        )

    @staticmethod
    def should_count_auth_failure(auth_result: dict[str, Any]) -> bool:
        """
        Define se uma falha deve consumir o rate limit.

        Erros de conexão, configuração ou falhas internas não são culpa
        do usuário e, portanto, não incrementam o contador.
        """

        if auth_result.get("success"):
            return False

        error_code = auth_result.get("code")

        return (
            error_code
            not in AuthenticationService.RATE_LIMIT_IGNORED_ERROR_CODES
        )

    @staticmethod
    def register_rate_limit_failure(
        ip_key: str,
        user_key: str | None,
    ) -> tuple[bool, int]:
        """
        Registra a mesma falha nas proteções por IP e por usuário.

        Retorna:
            (algum_limite_foi_atingido, maior_tempo_restante)
        """

        ip_blocked, ip_remaining = (
            AuthenticationService.register_failed_attempt(
                key=ip_key,
                max_attempts=(
                    AuthenticationService
                    .RATE_LIMIT_IP_MAX_ATTEMPTS
                ),
            )
        )

        user_blocked = False
        user_remaining = 0

        if user_key:
            user_blocked, user_remaining = (
                AuthenticationService.register_failed_attempt(
                    key=user_key,
                    max_attempts=(
                        AuthenticationService
                        .RATE_LIMIT_USER_MAX_ATTEMPTS
                    ),
                )
            )

        blocked = ip_blocked or user_blocked

        remaining = max(
            ip_remaining,
            user_remaining,
        )

        return blocked, remaining

    # -------------------------------------------------------------------------
    # AUTENTICAÇÃO
    # -------------------------------------------------------------------------

    @staticmethod
    def authenticate(request):
        """
        Executa o fluxo completo de autenticação.
        """

        client_ip = AuthenticationService.get_client_ip(
            request
        )

        ip_key = AuthenticationService.generate_rate_limit_key(
            "ip",
            client_ip,
        )

        # ---------------------------------------------------------------------
        # Verifica bloqueio por IP antes de consultar o Active Directory.
        # ---------------------------------------------------------------------

        ip_blocked, ip_remaining = (
            AuthenticationService.get_rate_limit_status(
                ip_key
            )
        )

        if ip_blocked:
            logger.warning(
                "Login bloqueado por rate limit de IP. ip=%s",
                client_ip,
            )

            messages.error(
                request,
                AuthenticationService.get_rate_limit_message(
                    ip_remaining
                ),
            )

            return redirect("auth")

        # ---------------------------------------------------------------------
        # Lê o formulário e prepara a chave do usuário.
        # ---------------------------------------------------------------------

        form = AuthenticationService.read_form(
            request
        )

        username = form.get("username", "").strip()

        normalized_username = (
            AuthenticationService.normalize_username(
                username
            )
        )

        user_key = None

        if normalized_username:
            user_key = (
                AuthenticationService.generate_rate_limit_key(
                    "username",
                    normalized_username,
                )
            )

            # -----------------------------------------------------------------
            # Verifica bloqueio por usuário antes de consultar o AD.
            # -----------------------------------------------------------------

            user_blocked, user_remaining = (
                AuthenticationService.get_rate_limit_status(
                    user_key
                )
            )

            if user_blocked:
                logger.warning(
                    (
                        "Login bloqueado por rate limit de usuário. "
                        "username=%s"
                    ),
                    normalized_username,
                )

                messages.error(
                    request,
                    AuthenticationService.get_rate_limit_message(
                        user_remaining
                    ),
                )

                return redirect("auth")

        # ---------------------------------------------------------------------
        # Validação básica.
        #
        # Formulários vazios não consomem tentativas de autenticação.
        # ---------------------------------------------------------------------

        errors = AuthenticationService.form_validate(
            form
        )

        if errors:
            messages.warning(
                request,
                errors[0],
            )
            return redirect("auth")

        # ---------------------------------------------------------------------
        # Autenticação no Active Directory.
        # ---------------------------------------------------------------------

        auth_result = AuthenticationService.authenticate_ad(
            username=form["username"],
            password=form["password"],
        )

        # ---------------------------------------------------------------------
        # Falha de autenticação.
        # ---------------------------------------------------------------------

        if not auth_result["success"]:

            if AuthenticationService.should_count_auth_failure(
                auth_result
            ):
                blocked, remaining = (
                    AuthenticationService.register_rate_limit_failure(
                        ip_key=ip_key,
                        user_key=user_key,
                    )
                )

                if blocked:
                    logger.warning(
                        (
                            "Rate limit de autenticação atingido. "
                            "username=%s, ip=%s"
                        ),
                        normalized_username,
                        client_ip,
                    )

                    messages.error(
                        request,
                        AuthenticationService.get_rate_limit_message(
                            remaining
                        ),
                    )

                    return redirect("auth")

            messages.error(
                request,
                auth_result["message"],
            )

            return redirect("auth")

        # ---------------------------------------------------------------------
        # Dados retornados pelo AD.
        # ---------------------------------------------------------------------

        ad_user = auth_result["user"]

        if not ad_user:
            logger.warning(
                (
                    "Autenticação LDAP retornou sucesso sem dados "
                    "do usuário. username=%s"
                ),
                normalized_username,
            )

            messages.error(
                request,
                AuthenticationService.DEFAULT_AUTH_ERROR_MESSAGE,
            )

            return redirect("auth")

        # ---------------------------------------------------------------------
        # Login válido.
        #
        # Zera apenas o contador daquele usuário.
        # O contador de IP permanece intacto.
        # ---------------------------------------------------------------------

        AuthenticationService.reset_user_rate_limit(
            username
        )

        # ---------------------------------------------------------------------
        # Sincroniza os dados locais do usuário.
        # ---------------------------------------------------------------------

        user, created = User.objects.get_or_create(
            username=form["username"],
        )

        user.first_name = ad_user["first_name"]
        user.last_name = ad_user["last_name"]
        user.email = ad_user["email"]

        if created:
            user.set_unusable_password()

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

        # ---------------------------------------------------------------------
        # Cria a sessão do Django.
        # ---------------------------------------------------------------------

        login(
            request,
            user,
            backend=(
                "django.contrib.auth.backends."
                "ModelBackend"
            ),
        )

        messages.success(
            request,
            f"Bem-vindo, {user.get_full_name()}!",
        )

        # ---------------------------------------------------------------------
        # Redirecionamento pós-login.
        # ---------------------------------------------------------------------

        allowed_hosts = {
            request.get_host()
        }

        next_url = request.POST.get("next")

        is_safe = bool(next_url) and (
            url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts=allowed_hosts,
                require_https=request.is_secure(),
            )
        )

        if (
            request.user.profile.profile_type == "operator"
            and not request.user.is_superuser
        ):
            return redirect("list_task")

        if is_safe:
            return redirect(next_url)

        return redirect("home")

    # -------------------------------------------------------------------------
    # ACTIVE DIRECTORY
    # -------------------------------------------------------------------------

    @staticmethod
    def authenticate_ad(
        username: str,
        password: str,
    ) -> dict[str, Any]:
        """
        Autentica o usuário no Active Directory.

        Retorna um dicionário contendo:

        - success: indica se a autenticação foi bem-sucedida;
        - message: mensagem que poderá ser apresentada ao usuário;
        - code: código retornado pelo Active Directory;
        - user: dados do usuário autenticado.
        """

        try:
            domain_settings = DomainService.read_connection()

            tls_config = Tls(
                validate=ssl.CERT_REQUIRED,
                ca_certs_file=os.getenv("CERTIFICATE"),
            )

            ldap_host = os.getenv("DOMAIN_CONTROL")
            ldap_host02 = os.getenv("DOMAIN_CONTROL02")

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

            bind_user = (
                f"{username}@{domain_settings.domain_name}"
            )

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
                    error_code = (
                        AuthenticationService.get_ad_error_code(
                            conn.result
                        )
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

                ad_user = (
                    AuthenticationService.get_ad_user_data(
                        conn=conn,
                        username=username,
                        domain_name=(
                            domain_settings.domain_name
                        ),
                        search_base=(
                            domain_settings.search_base
                        ),
                    )
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
                    AuthenticationService
                    .LDAP_CONNECTION_ERROR_MESSAGE
                ),
                "code": "ldap_error",
                "user": None,
            }

        except (AttributeError, TypeError, ValueError):
            logger.exception(
                (
                    "Configuração inválida do domínio "
                    "durante o login de %s."
                ),
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
                (
                    "Erro inesperado durante a autenticação "
                    "do usuário %s."
                ),
                username,
            )

            return {
                "success": False,
                "message": (
                    AuthenticationService
                    .LDAP_CONNECTION_ERROR_MESSAGE
                ),
                "code": "unexpected_error",
                "user": None,
            }

    @staticmethod
    def get_ad_error_code(
        result: dict | None,
    ) -> str | None:
        """
        Extrai o código de erro retornado pelo Active Directory.

        Exemplo:
            AcceptSecurityContext error, data 533, v...
        """

        if not result:
            return None

        message = str(
            result.get("message", "")
        ).lower()

        match = re.search(
            r"\bdata\s+([0-9a-f]+)\b",
            message,
        )

        if not match:
            return None

        return match.group(1).lower()

    @staticmethod
    def get_ad_user_data(
        conn: Connection,
        username: str,
        domain_name: str,
        search_base: str,
    ) -> dict[str, str]:
        """
        Consulta os dados do usuário autenticado no Active Directory.
        """

        safe_username = escape_filter_chars(
            username
        )

        safe_user_principal_name = (
            escape_filter_chars(
                f"{username}@{domain_name}"
            )
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
                (
                    "A busca LDAP falhou para o usuário %s. "
                    "Resultado=%s"
                ),
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

        display_name = (
            AuthenticationService.get_ad_attr(
                entry,
                "displayName",
            )
        )

        first_name = (
            AuthenticationService.get_ad_attr(
                entry,
                "givenName",
            )
        )

        last_name = (
            AuthenticationService.get_ad_attr(
                entry,
                "sn",
            )
        )

        email = (
            AuthenticationService.get_ad_attr(
                entry,
                "mail",
            )
        )

        if display_name and not first_name:
            name_parts = display_name.split(
                maxsplit=1
            )

            first_name = name_parts[0]

            if (
                len(name_parts) > 1
                and not last_name
            ):
                last_name = name_parts[1]

        return {
            "first_name": (
                first_name
                or display_name
                or username
            ),
            "last_name": last_name or "",
            "email": email or "",
        }

    @staticmethod
    def get_ad_attr(
        entry,
        attribute_name: str,
    ) -> str:
        """
        Obtém um atributo LDAP como string.
        """

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

    # -------------------------------------------------------------------------
    # LOGOUT
    # -------------------------------------------------------------------------

    @staticmethod
    @login_required
    @require_POST
    def logout_service(request):
        """
        Finaliza a sessão atual.
        """

        logout(request)

        messages.success(
            request,
            "Logout efetuado com sucesso! Até mais 👋",
        )

        return redirect("auth")
