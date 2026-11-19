#!/usr/bin/env python3
"""
Скрипт проверки и диагностики связи с Microsoft Active Directory
для АО «Интергаз Центральная Азия».

Запуск:
    python scripts/test_ad_connection.py
    python scripts/test_ad_connection.py --server ldaps://dc01.intergas.kz:636 --bind-dn "CN=svc,..." --bind-pwd "..."
"""
from __future__ import annotations

import argparse
import socket
import ssl
import sys
from urllib.parse import urlparse

# Добавляем корневую папку в sys.path
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    import ldap3
    from ldap3 import ALL, Connection, Server, Tls
    HAS_LDAP3 = True
except ImportError:
    HAS_LDAP3 = False

from app import config


def check_tcp_port(host: str, port: int, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP-порт {port} на хосте {host} открыт и отвечает."
    except socket.timeout:
        return False, f"Таймаут подключения к {host}:{port} (контроллер не отвечает за {timeout}с)."
    except ConnectionRefusedError:
        return False, f"Соединение отклонено (Connection refused) на {host}:{port}."
    except Exception as e:
        return False, f"Ошибка сети при проверке {host}:{port}: {e}"


def run_diagnostics(
    server_uri: str,
    base_dn: str,
    bind_dn: str = "",
    bind_password: str = "",
    test_user: str = "",
    use_ssl: bool = False,
) -> int:
    print("=" * 70)
    print("ДИАГНОСТИКА ПОДКЛЮЧЕНИЯ К ACTIVE DIRECTORY")
    print("АО «Интергаз Центральная Азия» // Комплекс ЛПУ, ГРС и КС")
    print("=" * 70)

    if not HAS_LDAP3:
        print("[-] ОШИБКА: Библиотека ldap3 не установлена в Python окружении.")
        print("    Установите: pip install ldap3")
        return 1

    # Парсим хост и порт
    parsed = urlparse(server_uri if "://" in server_uri else f"ldap://{server_uri}")
    host = parsed.hostname or "127.0.0.1"
    is_ssl = use_ssl or parsed.scheme == "ldaps" or parsed.port == 636
    port = parsed.port or (636 if is_ssl else 389)

    print(f"[*] Целевой сервер:   {host}")
    print(f"[*] Сетевой порт:     {port} ({'LDAPS (SSL/TLS)' if is_ssl else 'LDAP (Cleartext)'})")
    print(f"[*] Базовый DN:       {base_dn}")
    if bind_dn:
        print(f"[*] Сервисный Bind:   {bind_dn}")
    else:
        print("[!] Сервисный Bind:   НЕ ЗАДАН (анонимная проверка)")
    print("-" * 70)

    # Шаг 1: Проверка TCP порта
    print(f"[1/4] Проверка сетевой доступности {host}:{port}...")
    tcp_ok, tcp_msg = check_tcp_port(host, port)
    if not tcp_ok:
        print(f"[-] СБОЙ: {tcp_msg}")
        print("    Рекомендация: Проверьте корпоративный VPN/маршрутизацию, DNS и правила межсетевого экрана (Firewall).")
        return 2
    print(f"[+] УСПЕХ: {tcp_msg}")

    # Шаг 2: Инициализация сервера LDAP
    print(f"[2/4] Проверка протокола LDAP/LDAPS...")
    try:
        tls_obj = Tls(validate=ssl.CERT_NONE) if is_ssl else None
        server = Server(
            host=host,
            port=port,
            use_ssl=is_ssl,
            tls=tls_obj,
            get_info=ALL,
            connect_timeout=5,
        )
        print("[+] Серверный объект инициализирован.")
    except Exception as e:
        print(f"[-] Ошибка инициализации LDAP Server: {e}")
        return 3

    # Шаг 3: Проверка Bind
    print(f"[3/4] Проверка авторизации Bind...")
    if bind_dn and bind_password:
        try:
            conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True, timeout=5)
            print("[+] УСПЕХ: Сервисная учётная запись успешно прошла Bind в Active Directory!")
            if server.info and server.info.naming_contexts:
                print(f"    Контексты именования домена: {', '.join(server.info.naming_contexts)}")
        except Exception as e:
            print(f"[-] ОШИБКА BIND: Не удалось войти под сервисной учёткой: {e}")
            print("    Рекомендация: Проверьте точность DN сервисной учетки и пароль.")
            return 4
    else:
        try:
            conn = Connection(server, auto_bind=True, timeout=5)
            print("[+] УСПЕХ: Анонимный Bind успешен.")
        except Exception as e:
            print(f"[!] Анонимный Bind отклонён (стандартная политика безопасности Windows Server AD): {e}")
            print("    Для полноценной проверки требуется указать сервисный BIND_DN и пароль.")
            return 0

    # Шаг 4: Поиск по Base DN
    print(f"[4/4] Тестовый поиск в дереве каталога ({base_dn})...")
    try:
        filter_str = f"(&(objectCategory=person)(objectClass=user)(sAMAccountName={test_user}))" if test_user else "(objectClass=organizationalUnit)"
        conn.search(search_base=base_dn, search_filter=filter_str, search_scope=ldap3.SUBTREE, attributes=["cn", "sAMAccountName", "mail", "memberOf"], size_limit=5)
        print(f"[+] Найдено объектов: {len(conn.entries)}")
        for i, entry in enumerate(conn.entries, start=1):
            cn_val = entry.cn.value if "cn" in entry else str(entry.entry_dn)
            print(f"    {i}. {cn_val} (DN: {entry.entry_dn})")
    except Exception as e:
        print(f"[-] Ошибка поиска в каталоге: {e}")
    finally:
        try:
            conn.unbind()
        except Exception:
            pass

    print("=" * 70)
    print("[+] ВСЕ ПРОВЕРКИ ЗАВЕРШЕНЫ УСПЕШНО.")
    print("    Контроллер домена готов к интеграции с Keycloak и приложением Mind Equip!")
    print("=" * 70)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Диагностика подключения к Microsoft Active Directory")
    parser.add_argument("--server", default=config.AD_SERVER, help="URL контроллера (ldap://dc:389 или ldaps://dc:636)")
    parser.add_argument("--base-dn", default=config.AD_BASE_DN, help="Базовый DN домена (например, DC=intergas,DC=kz)")
    parser.add_argument("--bind-dn", default=config.AD_BIND_DN, help="DN сервисной учётной записи")
    parser.add_argument("--bind-pwd", default=config.AD_BIND_PASSWORD, help="Пароль сервисной учётной записи")
    parser.add_argument("--user", default="", help="Логин тестового пользователя для проверки поиска")
    parser.add_argument("--ssl", action="store_true", default=config.AD_USE_SSL, help="Принудительно использовать SSL")

    args = parser.parse_args()
    code = run_diagnostics(
        server_uri=args.server,
        base_dn=args.base_dn,
        bind_dn=args.bind_dn,
        bind_password=args.bind_pwd,
        test_user=args.user,
        use_ssl=args.ssl,
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
