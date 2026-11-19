"""
Модуль интеграции с Microsoft Active Directory (AD / LDAP / LDAPS)
для АО «Интергаз Центральная Азия».

Реализует:
1. Прямую аутентификацию сотрудников по доменным учётным записям (sAMAccountName, UPN, NetBIOS) в реальном времени.
2. Автоматический отзыв доступа: при удалении или блокировке человека в AD вход в приложение блокируется мгновенно.
3. Сопоставление доменных групп AD с ролями системы:
   - GG_ICA_Mechanics / Domain Admins -> admin (Главный механик: паспортизация, QR)
   - GG_ICA_Engineers -> engineer (Сменный инженер: ТО, дефекты)
   - Любой сотрудник Active Directory предприятия -> operator (Просмотр оборудования, паспортов и графиков)
"""
from __future__ import annotations

import inspect
import logging
import ssl
from typing import Any, Optional
from urllib.parse import urlparse

try:
    import ldap3
    from ldap3 import ALL, ALL_ATTRIBUTES, Connection, Server, Tls
    from ldap3.core.exceptions import LDAPException
    HAS_LDAP3 = True
except ImportError:
    HAS_LDAP3 = False
    ldap3 = None  # type: ignore

from app import config

logger = logging.getLogger(__name__)


def clean_username(raw_username: str, default_domain: str = "ica.kz") -> tuple[str, str]:
    """
    Нормализует логин сотрудника:
    - 'ICA\\a.sarsembayev' -> ('a.sarsembayev', 'a.sarsembayev@ica.kz')
    - 'a.sarsembayev@ica.kz' -> ('a.sarsembayev', 'a.sarsembayev@ica.kz')
    - 'a.sarsembayev' -> ('a.sarsembayev', 'a.sarsembayev@ica.kz')
    """
    domain = default_domain or config.AD_DOMAIN or "ica.kz"
    clean = raw_username.strip()
    if "\\" in clean:
        parts = clean.split("\\", 1)
        sam = parts[1].strip()
        upn = f"{sam}@{domain}"
        return sam, upn

    if "@" in clean:
        parts = clean.split("@", 1)
        sam = parts[0].strip()
        upn = clean.lower()
        return sam, upn

    sam = clean
    upn = f"{sam}@{domain}"
    return sam, upn


def get_bind_candidates(bind_user: str, default_domain: str = "ica.kz") -> list[str]:
    """
    Формирует список вариантов логина для подключения к Active Directory (DN, UPN, NetBIOS):
    1. Исходный (например: dev_svc@ica.kz или CN=dev_svc,OU=...)
    2. UPN: login@ica.kz
    3. NetBIOS: ICA\\login
    4. sAMAccountName: login
    """
    u = bind_user.strip()
    if not u:
        return []
    domain = default_domain or config.AD_DOMAIN or "ica.kz"
    netbios = domain.split(".")[0].upper()

    candidates = [u]
    if "=" in u:
        return candidates

    if "@" in u:
        sam = u.split("@")[0].strip()
        candidates.append(f"{netbios}\\{sam}")
        candidates.append(sam)
    elif "\\" in u:
        sam = u.split("\\")[-1].strip()
        candidates.append(f"{sam}@{domain}")
        candidates.append(sam)
    else:
        candidates.append(f"{u}@{domain}")
        candidates.append(f"{netbios}\\{u}")
        candidates.append(u)

    return list(dict.fromkeys(candidates))


def normalize_bind_user(bind_user: str, default_domain: str = "ica.kz") -> str:
    candidates = get_bind_candidates(bind_user, default_domain)
    return candidates[0] if candidates else ""


def _parse_server_endpoint(server_uri: str, use_ssl: Optional[bool] = None) -> tuple[str, int, bool]:
    """
    Надёжно разбирает адрес контроллера домена:
    'ldaps://srv-dc-url1.ica.kz:636' -> ('srv-dc-url1.ica.kz', 636, True)
    'srv-dc-url1.ica.kz' -> ('srv-dc-url1.ica.kz', 636 if use_ssl else 389, use_ssl)
    """
    raw = server_uri.strip()
    parsed = urlparse(raw if "://" in raw else f"ldap://{raw}")
    host = parsed.hostname or raw
    is_ssl = use_ssl if use_ssl is not None else (parsed.scheme == "ldaps" or parsed.port == 636 or config.AD_USE_SSL)
    port = parsed.port or (636 if is_ssl else 389)
    return host, port, is_ssl


def _create_ldap_connection(server: Server, user: Optional[str] = None, password: Optional[str] = None, timeout: float = 4.0) -> Connection:
    """
    Совместимое создание LDAP Connection для любых версий ldap3 без падений на аргументе timeout.
    """
    kwargs: dict[str, Any] = {"auto_bind": True}
    try:
        params = inspect.signature(Connection.__init__).parameters
        if "receive_timeout" in params:
            kwargs["receive_timeout"] = timeout
        elif "timeout" in params:
            kwargs["timeout"] = timeout
    except Exception:
        pass

    conn = Connection(server, user=user, password=password, **kwargs)
    try:
        conn.receive_timeout = timeout
    except Exception:
        pass
    return conn


def test_ad_connection(
    server_uri: Optional[str] = None,
    bind_dn: Optional[str] = None,
    bind_password: Optional[str] = None,
    use_ssl: Optional[bool] = None,
    timeout: int = 4,
) -> dict[str, Any]:
    """
    Проверяет сетевую доступность контроллера домена Active Directory
    и корректность авторизации (Bind) в реальном времени.
    """
    if not HAS_LDAP3:
        return {
            "success": False,
            "error": "Библиотека ldap3 не установлена в окружении Python.",
            "server": server_uri or config.AD_SERVER,
        }

    srv_uri = server_uri or config.AD_SERVER
    host, port, ssl_active = _parse_server_endpoint(srv_uri, use_ssl)

    try:
        tls_config = Tls(validate=ssl.CERT_NONE) if ssl_active else None
        server = Server(
            host=host,
            port=port,
            use_ssl=ssl_active,
            tls=tls_config,
            get_info=ALL,
            connect_timeout=timeout,
        )

        b_dn = bind_dn or config.AD_BIND_DN
        b_pwd = bind_password or config.AD_BIND_PASSWORD

        # Если задана учётная запись — проверяем Bind перебором UPN / NetBIOS
        if b_dn and b_pwd:
            conn = None
            last_err = None
            candidates = get_bind_candidates(b_dn, config.AD_DOMAIN)
            used_user = b_dn

            for candidate in candidates:
                try:
                    conn = _create_ldap_connection(server, user=candidate, password=b_pwd, timeout=timeout)
                    used_user = candidate
                    break
                except Exception as ex:
                    last_err = ex
                    continue

            if not conn:
                raise last_err or Exception(f"Не удалось войти в Active Directory под учетной записью {b_dn}")

            server_info = {
                "host": host,
                "port": port,
                "naming_contexts": list(server.info.naming_contexts) if server.info else [],
                "vendor": "Microsoft Active Directory",
                "ssl": ssl_active,
                "authenticated_as": used_user,
            }
            conn.unbind()
            return {
                "success": True,
                "message": f"Успешное подключение и авторизация в Active Directory как {used_user} на {host}:{port}",
                "server": f"{host}:{port}",
                "info": server_info,
            }

        # Анонимная проверка сокета/порта
        conn = _create_ldap_connection(server, timeout=timeout)
        conn.unbind()
        return {
            "success": True,
            "message": f"Порт контроллера домена {host}:{port} открыт и отвечает.",
            "server": f"{host}:{port}",
        }

    except Exception as e:
        logger.warning("Ошибка подключения к Active Directory (%s:%s): %s", host, port, e)
        return {
            "success": False,
            "error": str(e),
            "server": f"{host}:{port}",
            "help": "Проверьте сетевой доступ к порту 389/636, DNS контроллера домена и пароль учетной записи.",
        }


def _map_ad_groups_to_roles(member_of_list: list[str]) -> tuple[list[str], str]:
    """
    Сопоставляет группы безопасности Active Directory с ролями комплекса:
    1. GG_ICA_Mechanics / Domain Admins -> admin (Главный механик)
    2. GG_ICA_Engineers -> engineer (Сменный инженер)
    3. Любой сотрудник предприятия АО «Интергаз Центральная Азия» -> operator (Просмотр оборудования)
    """
    roles: list[str] = []
    groups_lower = [g.lower() for g in member_of_list]

    admin_group = config.AD_GROUP_ADMIN.lower()
    if any(admin_group in g or "domain admins" in g or "администраторы домена" in g for g in groups_lower):
        roles.append("admin")
        roles.append("engineer")

    engineer_group = config.AD_GROUP_ENGINEER.lower()
    if any(engineer_group in g for g in groups_lower):
        if "engineer" not in roles:
            roles.append("engineer")

    operator_group = config.AD_GROUP_OPERATOR.lower()
    if any(operator_group in g for g in groups_lower):
        if "operator" not in roles:
            roles.append("operator")

    # ГЛАВНОЕ ПРАВИЛО: любой доменный сотрудник компании получает безопасный доступ на просмотр (роль operator)
    if not roles:
        roles = ["operator"]

    if "admin" in roles:
        role_label = "Главный механик (AD: Администратор)"
    elif "engineer" in roles:
        role_label = "Инженер ТО и диагностики (AD)"
    else:
        role_label = "Оператор оборудования (AD: Сотрудник предприятия)"

    return roles, role_label


def authenticate_ad_user(username: str, password: str) -> Optional[dict[str, Any]]:
    """
    ЖИВАЯ АУТЕНТИФИКАЦИЯ В ACTIVE DIRECTORY (БЕЗ ЛОКАЛЬНЫХ ПАРОЛЕЙ).

    Каждый вход проверяется непосредственно на контроллере домена.
    Если пользователь удалён, заблокирован или истёк срок действия пароля в AD,
    он немедленно лишается доступа к приложению.
    """
    if not HAS_LDAP3:
        logger.error("ldap3 не установлен")
        return None

    if not config.AD_ENABLED or not password.strip():
        return None

    sam_name, upn_name = clean_username(username, default_domain=config.AD_DOMAIN)
    host, port, ssl_active = _parse_server_endpoint(config.AD_SERVER, config.AD_USE_SSL)

    try:
        tls_config = Tls(validate=ssl.CERT_NONE) if ssl_active else None
        server = Server(
            host=host,
            port=port,
            use_ssl=ssl_active,
            tls=tls_config,
            get_info=ALL,
            connect_timeout=3,
        )

        # 1. Живой Bind пользователя (пароль нигде не сохраняется)
        user_bind_success = False
        user_conn = None

        candidates = get_bind_candidates(username, config.AD_DOMAIN)
        for candidate in candidates:
            try:
                user_conn = _create_ldap_connection(server, user=candidate, password=password, timeout=3)
                user_bind_success = True
                break
            except Exception:
                continue

        if not user_bind_success or not user_conn:
            logger.info("Неудачная попытка входа в Active Directory для '%s'", sam_name)
            return None

        # 2. Чтение атрибутов и групп сотрудника
        read_conn = user_conn
        if config.AD_BIND_DN and config.AD_BIND_PASSWORD:
            for svc_candidate in get_bind_candidates(config.AD_BIND_DN, config.AD_DOMAIN):
                try:
                    svc_conn = _create_ldap_connection(server, user=svc_candidate, password=config.AD_BIND_PASSWORD, timeout=3)
                    read_conn = svc_conn
                    break
                except Exception:
                    pass

        search_base = config.AD_BASE_DN or "DC=ica,DC=kz"
        search_filter = f"(&(objectCategory=person)(objectClass=user)(sAMAccountName={sam_name}))"
        attributes = ["sAMAccountName", "displayName", "cn", "mail", "memberOf", "userPrincipalName", "objectGUID"]

        try:
            read_conn.search(
                search_base=search_base,
                search_filter=search_filter,
                search_scope=ldap3.SUBTREE,
                attributes=attributes,
            )
        except Exception as e_search:
            logger.warning("Ошибка поиска пользователя %s: %s", sam_name, e_search)

        display_name = sam_name
        email = f"{sam_name}@{config.AD_DOMAIN}"
        member_of: list[str] = []
        guid_str = f"ad-{sam_name}"

        if read_conn.entries:
            entry = read_conn.entries[0]
            if "displayName" in entry and entry.displayName.value:
                display_name = str(entry.displayName.value)
            elif "cn" in entry and entry.cn.value:
                display_name = str(entry.cn.value)

            if "mail" in entry and entry.mail.value:
                email = str(entry.mail.value)

            if "memberOf" in entry and entry.memberOf.values:
                member_of = [str(g) for g in entry.memberOf.values]

            if "objectGUID" in entry and entry.objectGUID.value:
                guid_str = str(entry.objectGUID.value)

        roles, role_label = _map_ad_groups_to_roles(member_of)

        try:
            user_conn.unbind()
        except Exception:
            pass

        return {
            "id": guid_str,
            "username": sam_name,
            "name": display_name,
            "email": email,
            "roles": roles,
            "role": roles[0],
            "role_label": role_label,
            "ad_groups": member_of,
            "auth_source": "active_directory",
            "is_ad_user": True,
        }

    except Exception as e:
        logger.error("Критический сбой аутентификации в Active Directory: %s", e)
        return None
