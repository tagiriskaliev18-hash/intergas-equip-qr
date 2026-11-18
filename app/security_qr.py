from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
import secrets
import threading
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import qrcode
from PIL import Image, ImageDraw, ImageFont

from app import config, storage

logger = logging.getLogger(__name__)

_lock = threading.RLock()


def _get_security_file() -> Path:
    docs_root = storage.get_docs_root()
    return docs_root / "security.json"


def _load_security_store() -> dict[str, Any]:
    sec_file = _get_security_file()
    if not sec_file.exists():
        return {"equipment_tokens": {}}
    try:
        data = json.loads(sec_file.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "equipment_tokens" not in data:
            return {"equipment_tokens": {}}
        return data
    except Exception as e:
        logger.warning("Ошибка чтения security.json: %s", e)
        return {"equipment_tokens": {}}


def _save_security_store(data: dict[str, Any]) -> None:
    sec_file = _get_security_file()
    sec_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = sec_file.with_suffix(".json.tmp")
    tmp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_file, sec_file)


def _compute_token(equipment_id: str, nonce: str) -> str:
    key = config.QR_SECRET_KEY.encode("utf-8")
    msg = f"{equipment_id}:{nonce}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:16].upper()


def get_or_create_secure_token(equipment_id: str) -> str:
    """
    Возвращает актуальный криптографический токен для агрегата.
    Если токена ещё нет, создаёт его и сохраняет в security.json.
    """
    storage.validate_safe_name(equipment_id)
    with _lock:
        store = _load_security_store()
        tokens = store.setdefault("equipment_tokens", {})
        if equipment_id in tokens and "token" in tokens[equipment_id]:
            return tokens[equipment_id]["token"]

        nonce = secrets.token_hex(8)
        token = _compute_token(equipment_id, nonce)
        now_iso = datetime.now(timezone.utc).isoformat()
        tokens[equipment_id] = {
            "token": token,
            "nonce": nonce,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        _save_security_store(store)
        return token


def rotate_secure_token(equipment_id: str) -> str:
    """
    Перевыпускает защищённый криптографический токен для оборудования
    (старый физический QR-стикер немедленно теряет валидность).
    """
    storage.validate_safe_name(equipment_id)
    with _lock:
        store = _load_security_store()
        tokens = store.setdefault("equipment_tokens", {})
        nonce = secrets.token_hex(8)
        token = _compute_token(equipment_id, nonce)
        now_iso = datetime.now(timezone.utc).isoformat()
        tokens[equipment_id] = {
            "token": token,
            "nonce": nonce,
            "created_at": tokens.get(equipment_id, {}).get("created_at", now_iso),
            "updated_at": now_iso,
        }
        _save_security_store(store)
        return token


def generate_secure_qr_payload(equipment_id: str) -> str:
    """
    Формирует закрытый payload:
    MINDEQUIP:v2:<equipment_id>:<token>
    Обычная камера смартфона не распознаёт его как ссылку и не переходит в браузер.
    Камера приложения Mind Equip валидирует токен и открывает карточку.
    """
    token = get_or_create_secure_token(equipment_id)
    return f"MINDEQUIP:v2:{equipment_id}:{token}"


def verify_secure_qr_token(scanned_text: str) -> dict[str, Any]:
    """
    Проверяет отсканированный QR-код.
    Поддерживает закрытый протокол MINDEQUIP:v2:... и MINDEQUIP:v1:...
    """
    raw = scanned_text.strip()
    if not raw.startswith("MINDEQUIP:"):
        return {
            "is_secure_qr": False,
            "valid": False,
            "error": "Не является защищённым QR-кодом оборудования Mind Equip",
            "equipment_id": None,
            "card_url": None,
        }

    parts = raw.split(":")
    if len(parts) < 4:
        return {
            "is_secure_qr": True,
            "valid": False,
            "error": "Неверный формат защищённого токена QR",
            "equipment_id": None,
            "card_url": None,
        }

    version = parts[1]
    equipment_id = parts[2]
    token = parts[3].upper()

    try:
        storage.validate_safe_name(equipment_id)
    except ValueError:
        return {
            "is_secure_qr": True,
            "valid": False,
            "error": "Недопустимый идентификатор оборудования",
            "equipment_id": None,
            "card_url": None,
        }

    record = storage.get_equipment(equipment_id)
    if not record:
        return {
            "is_secure_qr": True,
            "valid": False,
            "error": f"Агрегат '{equipment_id}' не найден в локальной базе",
            "equipment_id": None,
            "card_url": None,
        }

    with _lock:
        store = _load_security_store()
        tokens = store.get("equipment_tokens", {})
        entry = tokens.get(equipment_id)

    if not entry or entry.get("token") != token:
        # Проверяем, возможно токен ещё не был сохранён или совпадает с computed
        if entry:
            expected = _compute_token(equipment_id, entry.get("nonce", ""))
            if expected != token:
                return {
                    "is_secure_qr": True,
                    "valid": False,
                    "error": "Токен QR-кода устарел или был перевыпущен",
                    "equipment_id": equipment_id,
                    "card_url": None,
                }
        else:
            return {
                "is_secure_qr": True,
                "valid": False,
                "error": "Токен QR-кода не зарегистрирован в базе",
                "equipment_id": equipment_id,
                "card_url": None,
            }

    return {
        "is_secure_qr": True,
        "valid": True,
        "equipment_id": equipment_id,
        "equipment_name": record.name,
        "inventory_number": record.inventory_number,
        "card_url": f"/doc/{equipment_id}",
        "error": None,
    }


def generate_secure_qr_png(equipment_id: str) -> bytes:
    """
    Генерирует стикер с защищённым QR-кодом оборудования.
    Включает фирменную маркировку 'Mind Equip · Защищённый QR'
    и инвентарный номер агрегата.
    """
    record = storage.get_equipment(equipment_id)
    inv_num = record.inventory_number if record else equipment_id
    equip_name = record.name if record else equipment_id

    payload = generate_secure_qr_payload(equipment_id)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#09090F", back_color="#FFFFFF").convert("RGB")

    # Создаём аккуратный стикер с полями для печати
    padding = 24
    header_h = 44
    footer_h = 56
    total_w = qr_img.width + padding * 2
    total_h = qr_img.height + padding * 2 + header_h + footer_h

    sticker = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(sticker)

    # Загружаем шрифт
    font_path_bold = config.STATIC_DIR / "fonts" / "ReportSans-Bold.ttf"
    font_path_reg = config.STATIC_DIR / "fonts" / "ReportSans-Regular.ttf"

    try:
        font_header = ImageFont.truetype(str(font_path_bold), 15)
        font_sub = ImageFont.truetype(str(font_path_reg), 12)
        font_inv = ImageFont.truetype(str(font_path_bold), 16)
        font_warn = ImageFont.truetype(str(font_path_bold), 11)
    except Exception:
        font_header = font_sub = font_inv = font_warn = ImageFont.load_default()

    # Верхний заголовок стикера
    draw.text((padding, 14), "MIND EQUIP  ·  ЗАЩИЩЁННЫЙ КРИПТО-QR", fill=(75, 59, 255), font=font_header)
    draw.text((padding, 32), "Сканируется только камерой приложения", fill=(100, 110, 130), font=font_warn)

    # Вставка QR-кода
    qr_y = padding + header_h
    sticker.paste(qr_img, (padding, qr_y))

    # Нижняя плашка с инвентарным номером
    footer_y = qr_y + qr_img.height + 8
    draw.line([(padding, footer_y), (total_w - padding, footer_y)], fill=(220, 225, 235), width=1)
    draw.text((padding, footer_y + 8), f"ИНВ: {inv_num}", fill=(9, 9, 15), font=font_inv)

    short_name = equip_name[:42] + ("..." if len(equip_name) > 42 else "")
    draw.text((padding, footer_y + 30), short_name, fill=(80, 90, 110), font=font_sub)

    # Тонкая рамка по контуру
    draw.rectangle([(0, 0), (total_w - 1, total_h - 1)], outline=(190, 200, 215), width=2)

    buf = BytesIO()
    sticker.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
