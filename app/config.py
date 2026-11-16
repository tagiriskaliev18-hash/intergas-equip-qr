from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

HOST: str = os.getenv("QR_APP_HOST", "0.0.0.0")
PORT: int = int(os.getenv("QR_APP_PORT", "5810"))

DOCS_DIR: Path = Path(os.getenv("QR_DOCS_DIR", str(BASE_DIR / "documents"))).resolve()
CERTS_DIR: Path = Path(os.getenv("QR_CERTS_DIR", str(BASE_DIR / "certs"))).resolve()
STATIC_DIR: Path = BASE_DIR / "static"
TEMPLATES_DIR: Path = BASE_DIR / "templates"

CERT_FILE: Path = CERTS_DIR / "cert.pem"
KEY_FILE: Path = CERTS_DIR / "key.pem"
# Apple iOS / Safari отклоняет TLS-сертификаты со сроком действия > 825 дней
CERT_VALIDITY_DAYS: int = 365

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
