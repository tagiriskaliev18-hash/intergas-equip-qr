from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Сетевой адрес и порт (обновлено на 8443)
HOST: str = os.getenv("QR_APP_HOST", "0.0.0.0")
PORT: int = int(os.getenv("QR_APP_PORT", "8443"))

DOCS_DIR: Path = Path(os.getenv("QR_DOCS_DIR", str(BASE_DIR / "documents"))).resolve()
CERTS_DIR: Path = Path(os.getenv("QR_CERTS_DIR", str(BASE_DIR / "certs"))).resolve()
STATIC_DIR: Path = BASE_DIR / "static"
TEMPLATES_DIR: Path = BASE_DIR / "templates"

CERT_FILE: Path = CERTS_DIR / "cert.pem"
KEY_FILE: Path = CERTS_DIR / "key.pem"
# Apple iOS / Safari отклоняет TLS-сертификаты со сроком действия > 825 дней
CERT_VALIDITY_DAYS: int = 365

# Секрет для криптографической подписи защищённых QR-кодов (сканируются только камерой приложения)
QR_SECRET_KEY: str = os.getenv("QR_SECRET_KEY", "mind-equip-crypto-secret-key-2026")
SECURITY_FILE: Path = DOCS_DIR / "security.json"

# Keycloak OIDC настройки
KEYCLOAK_URL: str = os.getenv("KEYCLOAK_URL", "http://127.0.0.1:8080").rstrip("/")
KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "mind-equip")
KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID", "mind-equip-app")
KEYCLOAK_CLIENT_SECRET: str = os.getenv("KEYCLOAK_CLIENT_SECRET", "mind-equip-secret-2026-secure")
JWT_SECRET: str = os.getenv("JWT_SECRET", "mind-jwt-session-secret-key-2026-auth")
SESSION_COOKIE_NAME: str = "mind_session"

# Active Directory (AD / LDAP / LDAPS) настройки предприятия АО «Интергаз Центральная Азия»
AD_ENABLED: bool = os.getenv("AD_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on")
AD_SERVER: str = os.getenv("AD_SERVER", "ldap://127.0.0.1:389")
AD_DOMAIN: str = os.getenv("AD_DOMAIN", "intergas.kz")
AD_BASE_DN: str = os.getenv("AD_BASE_DN", "DC=intergas,DC=kz")
AD_USERS_OU: str = os.getenv("AD_USERS_OU", "OU=Users,OU=ICA,DC=intergas,DC=kz")
AD_BIND_DN: str = os.getenv("AD_BIND_DN", "")
AD_BIND_PASSWORD: str = os.getenv("AD_BIND_PASSWORD", "")
AD_USE_SSL: bool = os.getenv("AD_USE_SSL", "false").strip().lower() in ("1", "true", "yes", "on") or AD_SERVER.startswith("ldaps://")

# Доменные группы безопасности AD -> Роли в приложении
AD_GROUP_ADMIN: str = os.getenv("AD_GROUP_ADMIN", "GG_ICA_Mechanics")
AD_GROUP_ENGINEER: str = os.getenv("AD_GROUP_ENGINEER", "GG_ICA_Engineers")
AD_GROUP_OPERATOR: str = os.getenv("AD_GROUP_OPERATOR", "GG_ICA_Operators")

BUDGET_ALERT_HORIZON_DAYS: int = int(os.getenv("QR_BUDGET_HORIZON_DAYS", "30"))
URGENT_ALERT_HORIZON_DAYS: int = int(os.getenv("QR_URGENT_HORIZON_DAYS", "7"))

MAX_PDF_SIZE_BYTES: int = 50 * 1024 * 1024     # 50 МБ
MAX_PHOTO_SIZE_BYTES: int = 20 * 1024 * 1024   # 20 МБ

DOCUMENT_CATEGORIES: tuple[str, ...] = (
    "passport",
    "diagnostics",
    "schedule",
    "defects",
)

CATEGORY_TITLES: dict[str, str] = {
    "passport": "Паспорт оборудования",
    "diagnostics": "Документы диагностики",
    "schedule": "Графики и регламенты ТО",
    "defects": "Дефектные ведомости",
}
