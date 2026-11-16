from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from PIL import Image

from app import config
from app.models import (
    CompleteMaintenanceInput,
    ConditionState,
    DefectInput,
    DefectItem,
    DocumentFile,
    EquipmentCreateInput,
    EquipmentRecord,
    MaintenanceLogEntry,
    MaintenanceMaterial,
    MaintenanceMaterialInput,
    MaintenanceTask,
    MaintenanceTaskInput,
    PhotoInspection,
)

logger = logging.getLogger(__name__)

_REGISTRY_LOCK = threading.RLock()

_CYRILLIC_TRANSLIT: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def get_docs_root() -> Path:
    """
    Возвращает актуальный абсолютный путь к хранилищу документов.
    Всегда запрашивается динамически, чтобы работала подмена monkeypatch в тестах.
    """
    return config.DOCS_DIR.resolve()


def validate_safe_name(name: str) -> None:
    """
    Защита от Path Traversal: запрет символов перехода, разделителей путей и спецсимволов.
    """
    if not name or not isinstance(name, str):
        raise ValueError("Имя файла или идентификатора не может быть пустым")
    if ".." in name or "/" in name or "\\" in name or "\x00" in name:
        raise ValueError(f"Потенциально небезопасное имя: {name!r}")
    if any(ch in name for ch in ("\r", "\n", "\t")):
        raise ValueError(f"Недопустимые управляющие символы в имени: {name!r}")


def safe_resolve(*parts: str) -> Path:
    """
    Безопасно объединяет путь относительно корня documents,
    выполняя канонизацию и гарантируя, что путь не выходит за пределы get_docs_root().
    """
    for part in parts:
        validate_safe_name(part)
    root = get_docs_root()
    target = (root.joinpath(*parts)).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Обнаружена попытка выхода за пределы хранилища (Path Traversal): {parts!r}")
    return target


def slugify_id(text: str) -> str:
    """
    Транслитерирует русские символы и формирует безопасный slug
    по шаблону ^[a-z0-9][a-z0-9_-]{1,63}$.
    """
    s = text.strip().lower()
    translit_chars: list[str] = []
    for ch in s:
        if ch in _CYRILLIC_TRANSLIT:
            translit_chars.append(_CYRILLIC_TRANSLIT[ch])
        else:
            translit_chars.append(ch)
    joined = "".join(translit_chars)
    clean = re.sub(r"[^a-z0-9_\-]+", "-", joined)
    clean = re.sub(r"[\-_]+", "-", clean).strip("-_")

    if not clean:
        clean = f"eq-{uuid4().hex[:6]}"
    elif not clean[0].isalnum():
        clean = f"eq-{clean}"

    if len(clean) < 2:
        clean = f"{clean}-0"

    slug = clean[:64].rstrip("-_")
    if len(slug) < 2:
        slug = f"{slug}0"

    return slug


def format_size_ru(size_bytes: int) -> str:
    """
    Форматирует размер файла в удобочитаемый русский формат (Б, КБ, МБ).
    """
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    return f"{size_bytes / (1024 * 1024):.1f} МБ"


def _read_registry_unlocked() -> dict[str, EquipmentRecord]:
    reg_path = get_docs_root() / "registry.json"
    if not reg_path.exists():
        return {}
    try:
        data = json.loads(reg_path.read_text(encoding="utf-8"))
        records: dict[str, EquipmentRecord] = {}
        if isinstance(data, dict):
            for k, v in data.items():
                try:
                    records[k] = EquipmentRecord.model_validate(v)
                except Exception as e:
                    logger.warning("Ошибка валидации записи %s: %s", k, e)
        elif isinstance(data, list):
            for item in data:
                try:
                    rec = EquipmentRecord.model_validate(item)
                    records[rec.id] = rec
                except Exception as e:
                    logger.warning("Ошибка валидации элемента списка: %s", e)
        return records
    except Exception as e:
        logger.error("Ошибка чтения registry.json: %s", e)
        return {}


def _write_registry_unlocked(records: dict[str, EquipmentRecord]) -> None:
    root = get_docs_root()
    root.mkdir(parents=True, exist_ok=True)
    reg_path = root / "registry.json"
    reg_tmp = root / f"registry.json.tmp.{uuid4().hex}"

    dump_data = {eq_id: rec.model_dump(mode="json") for eq_id, rec in records.items()}
    encoded = json.dumps(dump_data, ensure_ascii=False, indent=2).encode("utf-8")

    try:
        reg_tmp.write_bytes(encoded)
        os.replace(str(reg_tmp), str(reg_path))
    finally:
        if reg_tmp.exists():
            try:
                reg_tmp.unlink()
            except OSError:
                pass


def list_equipment() -> list[EquipmentRecord]:
    """
    Возвращает список всех единиц оборудования из реестра.
    """
    with _REGISTRY_LOCK:
        records = _read_registry_unlocked()
        return list(records.values())


def get_equipment(equipment_id: str) -> EquipmentRecord | None:
    """
    Возвращает запись оборудования по его ID или None.
    """
    validate_safe_name(equipment_id)
    with _REGISTRY_LOCK:
        records = _read_registry_unlocked()
        return records.get(equipment_id)


def create_equipment(payload: EquipmentCreateInput) -> EquipmentRecord:
    """
    Создаёт новую единицу оборудования, валидирует уникальность ID
    и инициализирует стандартное дерево папок.
    """
    raw_id = payload.id.strip() if payload.id else payload.name.strip()
    equipment_id = slugify_id(raw_id)
    validate_safe_name(equipment_id)

    with _REGISTRY_LOCK:
        records = _read_registry_unlocked()
        if equipment_id in records:
            raise ValueError(f"Оборудование с идентификатором '{equipment_id}' уже существует")

        # Создание структуры каталогов
        for cat in (*config.DOCUMENT_CATEGORIES, "photos"):
            safe_resolve(equipment_id, cat).mkdir(parents=True, exist_ok=True)

        record = EquipmentRecord(
            id=equipment_id,
            name=payload.name.strip(),
            inventory_number=payload.inventory_number.strip(),
            model=payload.model.strip(),
            serial_number=payload.serial_number.strip(),
            manufacturer=payload.manufacturer.strip(),
            commission_year=payload.commission_year,
            location=payload.location.strip(),
            status=payload.status,
            maintenance_tasks=[],
            maintenance_history=[],
            defects=[],
            photos=[],
        )

        records[equipment_id] = record
        _write_registry_unlocked(records)
        return record


def list_documents(equipment_id: str) -> dict[str, list[DocumentFile]]:
    """
    Возвращает словарь списков локальных документов по категориям:
    passport, diagnostics, schedule, defects.
    Поддерживает обратную совместимость: если в корне equipment_id лежат *.pdf
    и подпапка passport/ пуста — они включаются в категорию passport.
    """
    validate_safe_name(equipment_id)
    result: dict[str, list[DocumentFile]] = {cat: [] for cat in config.DOCUMENT_CATEGORIES}

    for cat in config.DOCUMENT_CATEGORIES:
        cat_dir = safe_resolve(equipment_id, cat)
        files_found: list[Path] = []
        if cat_dir.exists() and cat_dir.is_dir():
            files_found = [p for p in cat_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]

        # Обратная совместимость для passport
        if cat == "passport" and not files_found:
            eq_root = safe_resolve(equipment_id)
            if eq_root.exists() and eq_root.is_dir():
                root_pdfs = [p for p in eq_root.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
                files_found.extend(root_pdfs)

        files_found.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        for p in files_found:
            fn = p.name
            stat = p.stat()
            size = stat.st_size
            dt_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            cat_literal: Any = cat
            doc = DocumentFile(
                filename=fn,
                category=cat_literal,
                category_title=config.CATEGORY_TITLES.get(cat, cat),
                size_bytes=size,
                size_human=format_size_ru(size),
                modified_at=dt_str,
                download_url=f"/files/{equipment_id}/{cat}/{quote(fn)}?download=1",
                view_url=f"/files/{equipment_id}/{cat}/{quote(fn)}?inline=1",
            )
            result[cat].append(doc)

    return result


def save_pdf_document(equipment_id: str, category: str, filename: str, content: bytes) -> DocumentFile:
    """
    Сохраняет загруженный или сгенерированный PDF-документ оборудования в соответствующую категорию.
    Проверяет категорию, заголовок %PDF-, размер и защищает от Path Traversal.
    """
    validate_safe_name(equipment_id)
    if category not in config.DOCUMENT_CATEGORIES:
        raise ValueError(f"Недопустимая категория документа: '{category}'")

    if not content:
        raise ValueError("Файл не может быть пустым")
    if len(content) > config.MAX_PDF_SIZE_BYTES:
        raise ValueError(f"Размер PDF превышает лимит {format_size_ru(config.MAX_PDF_SIZE_BYTES)}")

    if content.lstrip()[:5] != b"%PDF-":
        raise ValueError("Файл не является валидным документом PDF (отсутствует сигнатура %PDF-)")

    # Очистка имени файла с сохранением кириллицы/латиницы/цифр
    raw_name = Path(filename).name.strip()
    clean_name = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ\s\-_\.]", "_", raw_name)
    clean_name = re.sub(r"\s+", " ", clean_name).strip()
    if not clean_name.lower().endswith(".pdf"):
        clean_name = f"{clean_name}.pdf"
    if clean_name.lower() == ".pdf":
        clean_name = f"document_{uuid4().hex[:6]}.pdf"

    validate_safe_name(clean_name)
    target_path = safe_resolve(equipment_id, category, clean_name)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)

    stat = target_path.stat()
    dt_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    cat_literal: Any = category
    return DocumentFile(
        filename=clean_name,
        category=cat_literal,
        category_title=config.CATEGORY_TITLES.get(category, category),
        size_bytes=len(content),
        size_human=format_size_ru(len(content)),
        modified_at=dt_str,
        download_url=f"/files/{equipment_id}/{category}/{quote(clean_name)}?download=1",
        view_url=f"/files/{equipment_id}/{category}/{quote(clean_name)}?inline=1",
    )


def save_photo_inspection(
    equipment_id: str,
    filename: str,
    content: bytes,
    condition: ConditionState,
    node: str,
    comment: str,
) -> PhotoInspection:
    """
    Сохраняет фотографию осмотра технического состояния:
    валидирует формат (JPEG, PNG, WEBP) через Pillow, лимит размера,
    сохраняет файл в photos/, обновляет статус оборудования и добавляет запись в photos.
    """
    validate_safe_name(equipment_id)
    if not content:
        raise ValueError("Файл фотографии пуст")
    if len(content) > config.MAX_PHOTO_SIZE_BYTES:
        raise ValueError(f"Размер фото превышает лимит {format_size_ru(config.MAX_PHOTO_SIZE_BYTES)}")

    try:
        img = Image.open(BytesIO(content))
        img.verify()
        img_format = (img.format or "").upper()
        if img_format not in ("JPEG", "PNG", "WEBP"):
            raise ValueError(f"Неподдерживаемый формат изображения: {img_format} (разрешены JPEG, PNG, WEBP)")
    except Exception as e:
        raise ValueError(f"Некорректный файл изображения: {e}")

    ext_map = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}
    ext = ext_map.get(img_format, ".jpg")

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_fn = f"{timestamp_str}_{uuid4().hex[:6]}{ext}"
    validate_safe_name(clean_fn)

    target_path = safe_resolve(equipment_id, "photos", clean_fn)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)

    with _REGISTRY_LOCK:
        records = _read_registry_unlocked()
        record = records.get(equipment_id)
        if not record:
            raise ValueError(f"Оборудование с ID '{equipment_id}' не найдено")

        photo_id = f"photo-{uuid4().hex[:8]}"
        created_at_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        photo = PhotoInspection(
            id=photo_id,
            filename=clean_fn,
            created_at=created_at_str,
            condition=condition,
            node=node.strip(),
            comment=comment.strip(),
            url=f"/files/{equipment_id}/photos/{quote(clean_fn)}?inline=1",
            size_human=format_size_ru(len(content)),
        )

        record.status = condition
        record.photos.insert(0, photo)
        records[equipment_id] = record
        _write_registry_unlocked(records)
        return photo


def resolve_stored_file(equipment_id: str, folder: str, filename: str) -> Path:
    """
    Разрешает и проверяет существование файла в указанной папке оборудования.
    Защищает от Path Traversal и поддерживает fallback для passport из корня агрегата.
    """
    validate_safe_name(equipment_id)
    validate_safe_name(folder)
    validate_safe_name(filename)

    allowed_folders = (*config.DOCUMENT_CATEGORIES, "photos")
    if folder not in allowed_folders:
        raise ValueError(f"Недопустимая папка хранилища: {folder!r}")

    primary_path = safe_resolve(equipment_id, folder, filename)
    if primary_path.exists() and primary_path.is_file():
        return primary_path

    # Fallback для обратной совместимости passport в корне оборудования
    if folder == "passport":
        fallback_path = safe_resolve(equipment_id, filename)
        if fallback_path.exists() and fallback_path.is_file():
            return fallback_path

    raise FileNotFoundError(f"Файл не найден: {equipment_id}/{folder}/{filename}")


def upsert_maintenance_task(
    equipment_id: str,
    payload: MaintenanceTaskInput,
    task_id: str | None = None,
) -> MaintenanceTask:
    """
    Добавляет или обновляет регламентное задание ТО и перечень материалов/ЗИП.
    """
    validate_safe_name(equipment_id)
    with _REGISTRY_LOCK:
        records = _read_registry_unlocked()
        record = records.get(equipment_id)
        if not record:
            raise ValueError(f"Оборудование '{equipment_id}' не найдено")

        # Преобразование материалов
        converted_materials: list[MaintenanceMaterial] = []
        for m_in in payload.materials:
            m_id = f"mat-{uuid4().hex[:6]}"
            converted_materials.append(
                MaintenanceMaterial(
                    id=m_id,
                    name=m_in.name.strip(),
                    sku=m_in.sku.strip(),
                    unit=m_in.unit.strip(),
                    qty_required=m_in.qty_required,
                    qty_in_stock=m_in.qty_in_stock,
                    unit_price_rub=m_in.unit_price_rub,
                )
            )

        existing_task: MaintenanceTask | None = None
        if task_id:
            for t in record.maintenance_tasks:
                if t.id == task_id:
                    existing_task = t
                    break
        else:
            for t in record.maintenance_tasks:
                if t.code.strip().lower() == payload.code.strip().lower():
                    existing_task = t
                    break

        if existing_task:
            existing_task.code = payload.code.strip()
            existing_task.title = payload.title.strip()
            existing_task.interval_days = payload.interval_days
            existing_task.next_due_date = payload.next_due_date
            existing_task.responsible = payload.responsible.strip()
            existing_task.service_cost_rub = payload.service_cost_rub
            existing_task.notes = payload.notes.strip()
            if payload.last_completed_date is not None:
                existing_task.last_completed_date = payload.last_completed_date
            existing_task.materials = converted_materials
            result_task = existing_task
        else:
            new_id = task_id or f"task-{slugify_id(payload.code)}"
            result_task = MaintenanceTask(
                id=new_id,
                code=payload.code.strip(),
                title=payload.title.strip(),
                interval_days=payload.interval_days,
                last_completed_date=payload.last_completed_date,
                next_due_date=payload.next_due_date,
                responsible=payload.responsible.strip(),
                service_cost_rub=payload.service_cost_rub,
                materials=converted_materials,
                notes=payload.notes.strip(),
            )
            record.maintenance_tasks.append(result_task)

        records[equipment_id] = record
        _write_registry_unlocked(records)
        return result_task


def complete_maintenance_task(
    equipment_id: str,
    task_id: str,
    payload: CompleteMaintenanceInput,
) -> EquipmentRecord:
    """
    Фиксирует факт выполнения ТО:
    - проставляет last_completed_date,
    - сдвигает next_due_date на + interval_days от даты выполнения,
    - списывает остаток ТМЦ (или пополняет при restock_used_materials=True),
    - вносит запись в историю ТО (maintenance_history).
    """
    validate_safe_name(equipment_id)
    with _REGISTRY_LOCK:
        records = _read_registry_unlocked()
        record = records.get(equipment_id)
        if not record:
            raise ValueError(f"Оборудование '{equipment_id}' не найдено")

        target_task: MaintenanceTask | None = None
        for t in record.maintenance_tasks:
            if t.id == task_id:
                target_task = t
                break
        if not target_task:
            raise ValueError(f"Задание ТО с ID '{task_id}' не найдено")

        comp_date_str = payload.completed_date or date.today().isoformat()
        try:
            comp_date = date.fromisoformat(comp_date_str)
        except ValueError:
            comp_date = date.today()
            comp_date_str = comp_date.isoformat()

        next_due = (comp_date + timedelta(days=target_task.interval_days)).isoformat()
        target_task.last_completed_date = comp_date_str
        target_task.next_due_date = next_due

        # Работа с материалами
        mat_cost = 0.0
        for mat in target_task.materials:
            used_qty = mat.qty_required
            mat_cost += used_qty * mat.unit_price_rub
            if payload.restock_used_materials:
                mat.qty_in_stock = max(mat.qty_in_stock, mat.qty_required)
            else:
                mat.qty_in_stock = max(0.0, round(mat.qty_in_stock - used_qty, 2))

        actual_cost = round(target_task.service_cost_rub + mat_cost, 2)

        log_entry = MaintenanceLogEntry(
            id=f"log-{uuid4().hex[:8]}",
            task_code=target_task.code,
            task_title=target_task.title,
            completed_at=comp_date_str,
            performer=payload.performer.strip() or "Дежурный инженер",
            actual_cost_rub=actual_cost,
            comment=payload.comment.strip(),
        )
        record.maintenance_history.insert(0, log_entry)

        records[equipment_id] = record
        _write_registry_unlocked(records)
        return record


def add_defect(equipment_id: str, payload: DefectInput) -> DefectItem:
    """
    Добавляет выявленный дефект:
    если severity == 'critical', переводит оборудование в статус 'critical';
    если severity == 'high' и текущий статус 'good', переводит в 'attention'.
    """
    validate_safe_name(equipment_id)
    with _REGISTRY_LOCK:
        records = _read_registry_unlocked()
        record = records.get(equipment_id)
        if not record:
            raise ValueError(f"Оборудование '{equipment_id}' не найдено")

        defect_id = f"def-{uuid4().hex[:8]}"
        created_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        defect = DefectItem(
            id=defect_id,
            node=payload.node.strip(),
            description=payload.description.strip(),
            severity=payload.severity,
            recommended_action=payload.recommended_action.strip(),
            estimated_cost_rub=payload.estimated_cost_rub,
            photo_filename=payload.photo_filename,
            created_at=created_str,
            status="open",
        )

        if payload.severity == "critical":
            record.status = "critical"
        elif payload.severity == "high" and record.status == "good":
            record.status = "attention"

        record.defects.insert(0, defect)
        records[equipment_id] = record
        _write_registry_unlocked(records)
        return defect


def resolve_defect(equipment_id: str, defect_id: str) -> DefectItem:
    """
    Закрывает дефект (status = 'resolved') и при необходимости пересчитывает статус агрегата.
    """
    validate_safe_name(equipment_id)
    with _REGISTRY_LOCK:
        records = _read_registry_unlocked()
        record = records.get(equipment_id)
        if not record:
            raise ValueError(f"Оборудование '{equipment_id}' не найдено")

        target_defect: DefectItem | None = None
        for d in record.defects:
            if d.id == defect_id:
                target_defect = d
                break
        if not target_defect:
            raise ValueError(f"Дефект с ID '{defect_id}' не найден")

        target_defect.status = "resolved"

        # Проверка остальных открытых дефектов для статуса
        open_crit = any(d.status == "open" and d.severity == "critical" for d in record.defects)
        open_high = any(d.status == "open" and d.severity == "high" for d in record.defects)
        if open_crit:
            record.status = "critical"
        elif open_high:
            record.status = "attention"
        else:
            if record.photos:
                record.status = record.photos[0].condition
            else:
                record.status = "good"

        records[equipment_id] = record
        _write_registry_unlocked(records)
        return target_defect
