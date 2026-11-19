"""
Модуль интеграции с Microsoft Active Directory (AD / LDAP / LDAPS)
для АО «Интергаз Центральная Азия».

Реализует:
1. Прямую аутентификацию сотрудников по доменным учётным записям (sAMAccountName, UPN).
2. Чтение атрибутов пользователя (ФИО, E-mail, членство в доменных группах безопасности memberOf).
3. Сопоставление доменных групп AD с ролями системы (admin, engineer, operator).
4. Проверку сетевого соединения и диагностику связи с контроллером домена.
"""
from __future__ import annotations

import logging
import ssl
from typing import Any, Optional

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


def clean_username(raw_username: str, default_domain: str = "intergas.kz") -> tuple[str, str]:
    """
    Нормализует логин сотрудника:
    - 'INTERGAS\\a.sarsembayev' -> ('a.sarsembayev', 'a.sarsembayev@intergas.kz')
    - 'a.sarsembayev@intergas.kz' -> ('a.sarsembayev', 'a.sarsembayev@intergas.kz')
    - 'a.sarsembayev' -> ('a.sarsembayev', 'a.sarsembayev@intergas.kz')
    """
    clean = raw_username.strip()
    if "\\" in clean:
        parts = clean.split("\\", 1)
        sam = parts[1].strip()
        domain = parts[0].strip().lower()
        upn = f"{sam}@{default_domain}"
        return sam, upn

    if "@" in clean:
        parts = clean.split("@", 1)
        sam = parts[0].strip()
        upn = clean.lower()
        return sam, upn

    sam = clean
    upn = f"{sam}@{default_domain}"
    return sam, upn


def normalize_bind_user(bind_user: str, default_domain: str = "intergas.kz") -> str:
    """
    Приводит сервисный логин к подходящему для Active Directory виду:
    - 'CN=svc,OU=...' -> без изменений (Distinguished Name)
    - 'svc@intergas.kz' -> без изменений (UPN)
    - 'INTERGAS\\svc' -> без изменений (Downlevel)
    - 'svc' -> 'svc@intergas.kz' (автоматически дополняет UPN домена)
    """
    u = bind_user.strip()
    if not u:
        return ""
    if "=" in u or "@" in u or "\\" in u:
        return u
    return f"{u}@{default_domain}"


def test_ad_connection(
    server_uri: Optional[str] = None,
    bind_dn: Optional[str] = None,
    bind_password: Optional[str] = None,
    use_ssl: Optional[bool] = None,
    timeout: int = 4,
) -> dict[str, Any]:
    """
    Проверяет сетевую доступность контроллера домена Active Directory
    и корректность сервисной учётной записи (Bind).
    """
    if not HAS_LDAP3:
        return {
            "success": False,
            "error": "Библиотека ldap3 не установлена в окружении Python.",
            "server": server_uri or config.AD_SERVER,
        }

    srv_uri = server_uri or config.AD_SERVER
    ssl_active = use_ssl if use_ssl is not None else (config.AD_USE_SSL or srv_uri.startswith("ldaps://"))

    try:
        tls_config = None
        if ssl_active:
            tls_config = Tls(validate=ssl.CERT_NONE)

        server = Server(
            srv_uri,
            use_ssl=ssl_active,
            tls=tls_config,
            get_info=ALL,
            connect_timeout=timeout,
        )

        b_dn = normalize_bind_user(bind_dn or config.AD_BIND_DN, config.AD_DOMAIN)
        b_pwd = bind_password or config.AD_BIND_PASSWORD

        # Если задана сервисная учётная запись — проверяем Bind
        if b_dn and b_pwd:
            conn = Connection(server, user=b_dn, password=b_pwd, auto_bind=True, timeout=timeout)
            server_info = {
                "naming_contexts": list(server.info.naming_contexts) if server.info else [],
                "vendor": "Microsoft Active Directory",
                "ssl": ssl_active,
            }
            conn.unbind()
            return {
                "success": True,
                "message": f"Успешное подключение и авторизация сервисной учётной записи на {srv_uri}",
                "server": srv_uri,
                "info": server_info,
            }

        # Анонимная проверка доступности сокета/порта
        conn = Connection(server, auto_bind=True, timeout=timeout)
        conn.unbind()
        return {
            "success": True,
            "message": f"Порт контроллера домена {srv_uri} доступен по сети (Bind не проверялся, т.к. учетка не задана).",
            "server": srv_uri,
        }

    except Exception as e:
        logger.warning("Ошибка проверки подключения к Active Directory (%s): %s", srv_uri, e)
        return {
            "success": False,
            "error": str(e),
            "server": srv_uri,
            "help": "Проверьте сетевой доступ к порту 389/636, доступность DNS контроллера домена и параметры Bind DN.",
        }


def _map_ad_groups_to_roles(member_of_list: list[str]) -> tuple[list[str], str]:
    """
    Сопоставляет доменные группы безопасности AD с ролями приложения.
    """
    roles: list[str] = []
    groups_lower = [g.lower() for g in member_of_list]

    # Проверка на администратора (Главный механик)
    admin_group = config.AD_GROUP_ADMIN.lower()
    if any(admin_group in g or "domain admins" in g or "администраторы домена" in g for g in groups_lower):
        roles.append("admin")
        roles.append("engineer")

    # Проверка на инженера ТО / мастера
    engineer_group = config.AD_GROUP_ENGINEER.lower()
    if any(engineer_group in g for g in groups_lower):
        if "engineer" not in roles:
            roles.append("engineer")

    # Проверка на оператора
    operator_group = config.AD_GROUP_OPERATOR.lower()
    if any(operator_group in g for g in groups_lower):
        if "operator" not in roles:
            roles.append("operator")

    # Если сотрудник состоит в домене, но в явных группах не указан — выдаём роль оператора (безопасный просмотр)
    if not roles:
        roles = ["operator"]

    # Определяем понятный русский титул роли
    if "admin" in roles:
        role_label = "Главный механик (AD: Администратор)"
    elif "engineer" in roles:
        role_label = "Инженер ТО и диагностики (AD)"
    else:
        role_label = "Оператор оборудования (AD: Наблюдатель)"

    return roles, role_label


def authenticate_ad_user(username: str, password: str) -> Optional[dict[str, Any]]:
    """
    Выполняет аутентификацию сотрудника АО «Интергаз Центральная Азия»
    непосредственно в Active Directory.

    Возвращает словарь данных пользователя или None при неверном пароле/ошибке.
    """
    if not HAS_LDAP3:
        logger.error("Попытка аутентификации через AD, но ldap3 не установлен")
        return None

    if not config.AD_ENABLED or not password.strip():
        return None

    sam_name, upn_name = clean_username(username, default_domain=config.AD_DOMAIN)

    srv_uri = config.AD_SERVER
    ssl_active = config.AD_USE_SSL or srv_uri.startswith("ldaps://")

    try:
        tls_config = Tls(validate=ssl.CERT_NONE) if ssl_active else None
        server = Server(
            srv_uri,
            use_ssl=ssl_active,
            tls=tls_config,
            get_info=ALL,
            connect_timeout=3,
        )

        # 1. Проверяем подлинность пароля пользователя через User Bind
        user_bind_success = False
        user_conn = None

        # Пробуем UPN (user@intergas.kz)
        try:
            user_conn = Connection(server, user=upn_name, password=password, auto_bind=True, timeout=3)
            user_bind_success = True
        except Exception as e_upn:
            logger.debug("Bind по UPN '%s' не удался: %s", upn_name, e_upn)

        # Если не вышло — пробуем DOMAIN\username
        if not user_bind_success:
            domain_prefix = config.AD_DOMAIN.split(".")[0].upper()
            downlevel_name = f"{domain_prefix}\\{sam_name}"
            try:
                user_conn = Connection(server, user=downlevel_name, password=password, auto_bind=True, timeout=3)
                user_bind_success = True
            except Exception as e_downlevel:
                logger.debug("Bind по Downlevel '%s' не удался: %s", downlevel_name, e_downlevel)

        if not user_bind_success or not user_conn:
            logger.info("Неудачная попытка входа в AD для пользователя '%s'", sam_name)
            return None

        # 2. Извлекаем атрибуты пользователя (ФИО, почту, memberOf)
        # Если есть сервисная учётка — используем её, иначе читаем через текущее соединение
        read_conn = user_conn
        if config.AD_BIND_DN and config.AD_BIND_PASSWORD:
            svc_bind_user = normalize_bind_user(config.AD_BIND_DN, config.AD_DOMAIN)
            try:
                svc_conn = Connection(server, user=svc_bind_user, password=config.AD_BIND_PASSWORD, auto_bind=True, timeout=3)
                read_conn = svc_conn
            except Exception as e_svc:
                logger.warning("Не удалось открыть сервисное соединение AD (%s), читаем через пользователя: %s", svc_bind_user, e_svc)

        search_base = config.AD_BASE_DN
        search_filter = f"(&(objectCategory=person)(objectClass=user)(sAMAccountName={sam_name}))"
        attributes = ["sAMAccountName", "displayName", "cn", "mail", "memberOf", "userPrincipalName", "objectGUID"]

        read_conn.search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=ldap3.SUBTREE,
            attributes=attributes,
        )

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
            elif "userPrincipalName" in entry and entry.userPrincipalName.value:
                email = str(entry.userPrincipalName.value)

            if "memberOf" in entry and entry.memberOf.values:
                member_of = [str(g) for g in entry.memberOf.values]

            if "objectGUID" in entry and entry.objectGUID.value:
                guid_str = f"ad-{entry.objectGUID.value}"

        # Закрываем соединения
        try:
            user_conn.unbind()
        except Exception:
            pass
        if read_conn is not user_conn:
            try:
                read_conn.unbind()
            except Exception:
                pass

        # 3. Сопоставляем роли
        roles, role_label = _map_ad_groups_to_roles(member_of)

        logger.info(
            "Успешная AD-аутентификация: пользователь '%s' (%s), роли: %s",
            sam_name, display_name, roles
        )

        return {
            "sub": guid_str,
            "username": sam_name,
            "name": display_name,
            "email": email,
            "roles": roles,
            "role_label": role_label,
            "is_admin": "admin" in roles,
            "is_engineer": "engineer" in roles or "admin" in roles,
            "member_of": member_of,
            "auth_source": "Active Directory (LDAP)",
        }

    except Exception as e:
        logger.exception("Исключение при взаимодействии с Active Directory для '%s': %s", sam_name, e)
        return None
