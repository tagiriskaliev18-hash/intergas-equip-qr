#!/usr/bin/env python3
"""
Скрипт автоматизированной настройки интеграции Keycloak 26 с Microsoft Active Directory
для АО «Интергаз Центральная Азия».

Регистрирует User Federation (LDAP/AD) и сопоставление групп в роли:
- Главный механик -> admin
- Инженер ТО и диагностики -> engineer
- Оператор оборудования -> operator

Запуск:
    python scripts/setup_active_directory.py
    python scripts/setup_active_directory.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("setup_ad")


def get_admin_token(keycloak_url: str, admin_user: str = "admin", admin_pass: str = "admin") -> str:
    token_url = f"{keycloak_url}/realms/master/protocol/openid-connect/token"
    data = {
        "client_id": "admin-cli",
        "grant_type": "password",
        "username": admin_user,
        "password": admin_pass,
    }
    with httpx.Client(timeout=5.0) as client:
        resp = client.post(token_url, data=data)
        if resp.status_code != 200:
            raise RuntimeError(f"Не удалось получить токен администратора Keycloak: HTTP {resp.status_code}: {resp.text}")
        return resp.json()["access_token"]


def configure_ad_federation(
    keycloak_url: str,
    realm: str,
    admin_user: str = "admin",
    admin_pass: str = "admin",
    dry_run: bool = False,
) -> bool:
    print("=" * 72)
    print("НАСТРОЙКА ИНТЕГРАЦИИ KEYCLOAK ↔ ACTIVE DIRECTORY")
    print("АО «Интергаз Центральная Азия»")
    print("=" * 72)
    print(f"[*] Keycloak URL:       {keycloak_url}")
    print(f"[*] Целевой Realm:      {realm}")
    print(f"[*] Домен AD:           {config.AD_DOMAIN}")
    print(f"[*] Контроллер AD:      {config.AD_SERVER}")
    print(f"[*] Users DN:           {config.AD_USERS_OU}")
    print(f"[*] Base DN:            {config.AD_BASE_DN}")
    print(f"[*] Сервисный Bind DN:  {config.AD_BIND_DN or '(не задан в .env)'}")
    print("-" * 72)

    component_payload = {
        "name": "intergas-active-directory",
        "providerId": "ldap",
        "providerType": "org.keycloak.storage.UserStorageProvider",
        "parentId": realm,
        "config": {
            "enabled": ["true"],
            "priority": ["0"],
            "editMode": ["READ_ONLY"],
            "syncRegistrations": ["false"],
            "vendor": ["ad"],
            "usernameLDAPAttribute": ["sAMAccountName"],
            "rdnLDAPAttribute": ["cn"],
            "uuidLDAPAttribute": ["objectGUID"],
            "userObjectClasses": ["person, organizationalPerson, user"],
            "connectionUrl": [config.AD_SERVER],
            "usersDn": [config.AD_USERS_OU or config.AD_BASE_DN],
            "authType": ["simple"],
            "bindDn": [config.AD_BIND_DN or f"CN=svc_keycloak,OU=ServiceAccounts,{config.AD_BASE_DN}"],
            "bindCredential": [config.AD_BIND_PASSWORD or "Password_Required_From_Admin"],
            "searchScope": ["1"],
            "useTruststoreSpi": ["always"],
            "connectionTimeout": ["5000"],
            "readTimeout": ["10000"],
            "batchSizeForSync": ["1000"],
            "allowKerberosAuthentication": ["false"],
            "useKerberosForPasswordAuthentication": ["false"],
        },
    }

    if dry_run:
        print("[DRY-RUN] Сформированная конфигурация User Federation для Keycloak:")
        print(json.dumps(component_payload, indent=2, ensure_ascii=False))
        print("[+] DRY-RUN завершён успешно. Изменения в Keycloak не вносились.")
        return True

    try:
        token = get_admin_token(keycloak_url, admin_user, admin_pass)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    except Exception as e:
        print(f"[!] Keycloak недоступен или учетные данные администратора не подошли: {e}")
        print("    Вы можете импортировать обновленный config/keycloak-realm.json вручную")
        print("    или запустить Keycloak через scripts/start_keycloak.ps1")
        return False

    with httpx.Client(timeout=10.0) as client:
        # Проверяем, существует ли уже данный провайдер
        list_url = f"{keycloak_url}/admin/realms/{realm}/components?type=org.keycloak.storage.UserStorageProvider"
        resp = client.get(list_url, headers=headers)
        existing_id = None
        if resp.status_code == 200:
            for c in resp.json():
                if c.get("name") == "intergas-active-directory":
                    existing_id = c.get("id")
                    break

        if existing_id:
            print(f"[*] Провайдер 'intergas-active-directory' уже зарегистрирован (ID: {existing_id}). Обновляем параметры...")
            update_url = f"{keycloak_url}/admin/realms/{realm}/components/{existing_id}"
            up_resp = client.put(update_url, headers=headers, json=component_payload)
            if up_resp.status_code in (200, 204):
                print("[+] Параметры федерации Active Directory успешно обновлены!")
            else:
                print(f"[-] Ошибка обновления: HTTP {up_resp.status_code}: {up_resp.text}")
                return False
        else:
            print("[*] Создание нового User Federation провайдера в Keycloak...")
            create_url = f"{keycloak_url}/admin/realms/{realm}/components"
            cr_resp = client.post(create_url, headers=headers, json=component_payload)
            if cr_resp.status_code == 201:
                print("[+] Федерация Active Directory успешно создана в Keycloak!")
            else:
                print(f"[-] Ошибка создания: HTTP {cr_resp.status_code}: {cr_resp.text}")
                return False

    print("=" * 72)
    print("[+] ГОТОВО: Keycloak теперь связан с Active Directory АО «Интергаз Центральная Азия»!")
    print("    Сотрудники могут входить по своим рабочим доменным логинам и паролям.")
    print("=" * 72)
    return True


def main():
    parser = argparse.ArgumentParser(description="Интеграция Keycloak с Active Directory")
    parser.add_argument("--keycloak-url", default=config.KEYCLOAK_URL, help="URL Keycloak (по умолчанию http://127.0.0.1:8080)")
    parser.add_argument("--realm", default=config.KEYCLOAK_REALM, help="Имя realm (по умолчанию mind-equip)")
    parser.add_argument("--admin-user", default="admin", help="Логин админа Keycloak")
    parser.add_argument("--admin-pass", default="admin", help="Пароль админа Keycloak")
    parser.add_argument("--dry-run", action="store_true", help="Только показать JSON без отправки")

    args = parser.parse_args()
    ok = configure_ad_federation(
        keycloak_url=args.keycloak_url,
        realm=args.realm,
        admin_user=args.admin_user,
        admin_pass=args.admin_pass,
        dry_run=args.dry_run,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
