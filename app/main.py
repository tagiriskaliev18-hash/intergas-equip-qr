from __future__ import annotations

import logging
import mimetypes
import os
import re
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import config, notifications, pdf_generator, qr_service, storage
from app.models import (
    CompleteMaintenanceInput,
    ConditionState,
    DefectInput,
    DefectItem,
    DocumentFile,
    EquipmentCreateInput,
    EquipmentRecord,
    MaintenanceTask,
    MaintenanceTaskInput,
    PhotoInspection,
)
from app.ssl_manager import get_local_ipv4_addresses

logger = logging.getLogger("mind_equip")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Жизненный цикл приложения:
    при первом старте инициализирует демонстрационную базу (если не задан QR_DISABLE_AUTO_SEED=1).
    """
    if os.getenv("QR_DISABLE_AUTO_SEED") != "1":
        try:
            seeded = storage.get_docs_root().exists() and (storage.get_docs_root() / "registry.json").exists()
            if not seeded or not storage.list_equipment():
                from app.seed_demo import seed_demo_data_if_empty
                seed_demo_data_if_empty()
        except Exception as e:
            logger.warning("Ошибка автогенерации демонстрационных данных: %s", e)
    yield


app = FastAPI(
    title="Mind Equip — База документации и ТО оборудования",
    version="1.0.0",
    description="Локальный автономный узел технической документации, паспортизации и контроля ТО оборудования",
    lifespan=lifespan,
)

# Монтирование статических файлов (CSS, JS, Fonts, Vendor)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")

# Шаблоны Jinja2
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def _render_not_found(request: Request, equipment_id: str) -> Response:
    """
    Рендерит страницу 404.html при отсутствии оборудования или возвращает адаптивный fallback.
    """
    try:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={
                "request": request,
                "equipment_id": equipment_id,
                "message": "Оборудование не найдено",
            },
            status_code=status.HTTP_404_NOT_FOUND,
        )
    except Exception:
        fallback_html = (
            "<!DOCTYPE html><html lang='ru'><head><meta charset='UTF-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
            "<title>404 — Агрегат не найден // Mind Equip</title>"
            "<link rel='stylesheet' href='/static/css/styles.css'>"
            "</head><body style='background:#09090F;color:#F3F5FA;font-family:sans-serif;padding:40px;text-align:center;'>"
            "<h1 style='color:#00F5FF;'>404 — Оборудование не найдено</h1>"
            f"<p style='color:#8B93A7;'>Агрегат с идентификатором <code style='color:#F3F5FA;'>{equipment_id}</code> отсутствует в локальной базе.</p>"
            "<p style='margin-top:24px;'><a href='/' style='color:#00F5FF;text-decoration:none;'>← Вернуться к сканеру</a></p>"
            "</body></html>"
        )
        return HTMLResponse(content=fallback_html, status_code=status.HTTP_404_NOT_FOUND)


# =============================================================================
# HTML-маршруты (SPA и карточка оборудования)
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request) -> Response:
    """
    Главный экран (SPA):
    - кнопка запуска видеокамеры и QR-сканирования;
    - сводка уведомлений ТО и бюджета;
    - реестр оборудования.
    """
    lan_ips = get_local_ipv4_addresses()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "port": config.PORT,
            "lan_ips": lan_ips,
        },
    )


@app.get("/doc/{equipment_id}", response_class=HTMLResponse)
@app.get("/equipment/{equipment_id}", response_class=HTMLResponse)
async def equipment_page(request: Request, equipment_id: str) -> Response:
    """
    Карточка агрегата по ссылке из QR-кода:
    - 4 вкладки: Документы (PDF), ТО и бюджет, Фотоосмотр, Дефекты;
    - скачивание/печать QR-кода.
    """
    try:
        storage.validate_safe_name(equipment_id)
    except ValueError:
        return _render_not_found(request, equipment_id)

    record = storage.get_equipment(equipment_id)
    if not record:
        return _render_not_found(request, equipment_id)

    return templates.TemplateResponse(
        request=request,
        name="equipment.html",
        context={
            "request": request,
            "equipment_id": equipment_id,
            "equipment": record,
        },
    )


# =============================================================================
# Раздача локальных файлов (PDF и фото) с защитой от Path Traversal и RFC 5987
# =============================================================================

@app.get("/files/{equipment_id}/{category}/{filename}")
async def get_stored_file(
    equipment_id: str,
    category: str,
    filename: str,
    download: Optional[int] = Query(default=None),
    inline: Optional[int] = Query(default=None),
) -> Response:
    """
    Отдаёт локальный документ (PDF) или фотографию осмотра оборудования.
    Строгая защита от Path Traversal, проверка существования,
    формирование заголовков Content-Disposition (RFC 5987) и X-Content-Type-Options.
    """
    try:
        storage.validate_safe_name(equipment_id)
        storage.validate_safe_name(category)
        storage.validate_safe_name(filename)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    allowed_cats = (*config.DOCUMENT_CATEGORIES, "photos")
    if category not in allowed_cats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимая категория хранилища: {category!r}",
        )

    try:
        file_path = storage.resolve_stored_file(equipment_id, category, filename)
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Файл не найден")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    ext = file_path.suffix.lower()
    if ext == ".pdf":
        media_type = "application/pdf"
    elif ext in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif ext == ".png":
        media_type = "image/png"
    elif ext == ".webp":
        media_type = "image/webp"
    else:
        mime, _ = mimetypes.guess_type(str(file_path))
        media_type = mime or "application/octet-stream"

    # Определение типа disposition
    if inline == 1:
        disposition_type = "inline"
    elif download == 1:
        disposition_type = "attachment"
    elif category == "photos":
        disposition_type = "inline"
    else:
        disposition_type = "attachment"

    # Формирование заголовка RFC 5987
    ascii_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", file_path.name)
    encoded_name = quote(file_path.name)
    cd_header = f"{disposition_type}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"

    headers = {
        "Content-Disposition": cd_header,
        "X-Content-Type-Options": "nosniff",
    }
    return FileResponse(path=file_path, media_type=media_type, headers=headers)


# =============================================================================
# Системное API
# =============================================================================

@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
        "<rect width='32' height='32' rx='6' fill='#09090F' stroke='#4B3BFF' stroke-width='2'/>"
        "<text x='16' y='22' text-anchor='middle' fill='#F2F4F8' font-family='monospace' "
        "font-weight='700' font-size='18'>M</text></svg>"
    )
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/api/health")
async def health_check() -> dict[str, Any]:
    """
    Проверка работоспособности сервера.
    """
    return {
        "status": "ok",
        "host": config.HOST,
        "port": config.PORT,
    }


@app.get("/api/network-info")
async def network_info() -> dict[str, Any]:
    """
    Возвращает информацию о порте 5810 и доступных локальных IPv4-адресах для подключения по Wi-Fi.
    """
    lan_ips = get_local_ipv4_addresses()
    lan_urls = [f"https://{ip}:{config.PORT}" for ip in lan_ips]
    primary_url = lan_urls[0] if lan_urls else f"https://127.0.0.1:{config.PORT}"
    return {
        "host": config.HOST,
        "port": config.PORT,
        "lan_ips": lan_ips,
        "lan_urls": lan_urls,
        "primary_url": primary_url,
    }


@app.get("/404", response_class=HTMLResponse)
async def not_found_page(request: Request) -> Response:
    return _render_not_found(request, "—")


@app.get("/api/overview")
async def overview() -> dict[str, Any]:
    """
    Сводка по оборудованию, активные предупреждения о ТО и расчёт сумм в бюджет.
    """
    return notifications.build_overview()


# =============================================================================
# API Оборудования (Реестр, карточка, QR)
# =============================================================================

def _build_full_equipment_card(record: EquipmentRecord) -> dict[str, Any]:
    documents = storage.list_documents(record.id)
    evaluation = notifications.evaluate_equipment(record, docs=documents)
    return {
        "id": record.id,
        "status": record.status,
        "equipment": record,
        "record": record,
        "maintenance_tasks": record.maintenance_tasks,
        "maintenance_history": record.maintenance_history,
        "photos": record.photos,
        "defects": record.defects,
        "has_passport": evaluation["has_passport"],
        "has_diagnostics": evaluation["has_diagnostics"],
        "documents": documents,
        "evaluation": evaluation,
        "qr_url": f"/api/equipment/{record.id}/qr",
        "card_path": f"/doc/{record.id}",
    }


@app.post("/api/equipment", status_code=status.HTTP_201_CREATED)
async def create_equipment(
    payload: EquipmentCreateInput,
    auto_passport: bool = Query(default=True),
) -> dict[str, Any]:
    """
    Добавляет новую единицу оборудования в локальную базу.
    При auto_passport=True автоматически генерирует стартовый паспорт PDF.
    Возвращает статус 201 и полную карточку оборудования.
    """
    try:
        record = storage.create_equipment(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if auto_passport:
        try:
            pdf_bytes = pdf_generator.generate_passport_pdf(record)
            storage.save_pdf_document(
                equipment_id=record.id,
                category="passport",
                filename=f"passport_{record.id}.pdf",
                content=pdf_bytes,
            )
        except Exception as e:
            logger.warning("Не удалось сгенерировать стартовый паспорт для %s: %s", record.id, e)

    return _build_full_equipment_card(record)


@app.get("/api/equipment/{equipment_id}")
async def get_equipment(equipment_id: str) -> dict[str, Any]:
    """
    Возвращает полные данные карточки оборудования, локальные документы и бюджетную оценку.
    """
    try:
        storage.validate_safe_name(equipment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    return _build_full_equipment_card(record)


@app.get("/api/equipment/{equipment_id}/qr")
async def get_equipment_qr(
    equipment_id: str,
    request: Request,
    origin: Optional[str] = Query(default=None),
) -> Response:
    """
    Генерирует PNG QR-кода со ссылкой на карточку агрегата.
    """
    try:
        storage.validate_safe_name(equipment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    if origin:
        base_url = origin.rstrip("/")
    else:
        host_header = request.headers.get("host") or f"{config.HOST}:{config.PORT}"
        scheme = request.url.scheme or "https"
        base_url = f"{scheme}://{host_header}"

    target_url = f"{base_url}/doc/{equipment_id}"
    png_bytes = qr_service.generate_qr_png(target_url)

    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# =============================================================================
# API Документов (Загрузка PDF и фото)
# =============================================================================

@app.post(
    "/api/equipment/{equipment_id}/documents/{category}",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentFile,
)
async def upload_document(
    equipment_id: str,
    category: str,
    file: UploadFile = File(...),
) -> DocumentFile:
    """
    Загружает PDF-документ (паспорт, диагностика, график ТО, дефектная ведомость).
    Проверяет формат PDF, сигнатуру %PDF-, размер и сохраняет в локальный каталог.
    """
    if category not in config.DOCUMENT_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимая категория документа: {category!r}",
        )

    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    content = await file.read()
    try:
        doc = storage.save_pdf_document(
            equipment_id=equipment_id,
            category=category,
            filename=file.filename or "document.pdf",
            content=content,
        )
        return doc
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post(
    "/api/equipment/{equipment_id}/photos",
    status_code=status.HTTP_201_CREATED,
    response_model=PhotoInspection,
)
async def upload_photo(
    equipment_id: str,
    file: UploadFile = File(...),
    condition: ConditionState = Form("good"),
    node: str = Form(""),
    comment: str = Form(""),
) -> PhotoInspection:
    """
    Загружает фотографию технического состояния агрегата со смартфона:
    валидирует формат изображения, сохраняет в photos/, обновляет статус оборудования
    и добавляет запись в ленту осмотров.
    """
    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    content = await file.read()
    try:
        photo = storage.save_photo_inspection(
            equipment_id=equipment_id,
            filename=file.filename or "inspection.jpg",
            content=content,
            condition=condition,
            node=node,
            comment=comment,
        )
        return photo
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# API Технического обслуживания и материалов
# =============================================================================

@app.post(
    "/api/equipment/{equipment_id}/maintenance",
    status_code=status.HTTP_201_CREATED,
    response_model=MaintenanceTask,
)
async def upsert_maintenance(
    equipment_id: str,
    payload: MaintenanceTaskInput,
    task_id: Optional[str] = Query(default=None),
) -> MaintenanceTask:
    """
    Добавляет или обновляет регламентное задание ТО и перечень материалов/ЗИП.
    """
    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    try:
        task = storage.upsert_maintenance_task(equipment_id, payload, task_id=task_id)
        return task
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/equipment/{equipment_id}/maintenance/{task_id}/complete")
async def complete_maintenance(
    equipment_id: str,
    task_id: str,
    payload: CompleteMaintenanceInput,
) -> dict[str, Any]:
    """
    Фиксирует выполнение ТО:
    - пересчитывает дату следующего ТО;
    - обновляет остатки ТМЦ на складе;
    - вносит запись в историю ТО;
    - возвращает обновлённую карточку оборудования.
    """
    try:
        record = storage.complete_maintenance_task(equipment_id, task_id, payload)
        return _build_full_equipment_card(record)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# API Дефектов
# =============================================================================

@app.post(
    "/api/equipment/{equipment_id}/defects",
    status_code=status.HTTP_201_CREATED,
    response_model=DefectItem,
)
async def add_defect(
    equipment_id: str,
    payload: DefectInput,
) -> DefectItem:
    """
    Фиксирует выявленный дефект и при необходимости переводит агрегат в аварийный статус.
    """
    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    try:
        defect = storage.add_defect(equipment_id, payload)
        return defect
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post(
    "/api/equipment/{equipment_id}/defects/{defect_id}/resolve",
    response_model=DefectItem,
)
async def resolve_defect(
    equipment_id: str,
    defect_id: str,
) -> DefectItem:
    """
    Отмечает дефект как устранённый.
    """
    try:
        defect = storage.resolve_defect(equipment_id, defect_id)
        return defect
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# API Автогенерации PDF (Дефектные ведомости, графики ТО, бюджетные заявки)
# =============================================================================

@app.post(
    "/api/equipment/{equipment_id}/defects/generate-pdf",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentFile,
)
async def generate_defects_pdf(equipment_id: str) -> DocumentFile:
    """
    Автоматически генерирует оформленную дефектную ведомость в формате PDF,
    сохраняет её в каталог defects/ агрегата и возвращает метаданные файла.
    """
    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    pdf_bytes = pdf_generator.generate_defect_sheet_pdf(record)
    date_str = date.today().strftime("%Y%m%d")
    fn = f"defect_sheet_{record.id}_{date_str}.pdf"
    doc = storage.save_pdf_document(record.id, "defects", fn, pdf_bytes)
    return doc


@app.post(
    "/api/equipment/{equipment_id}/schedule/generate-pdf",
    status_code=status.HTTP_201_CREATED,
    response_model=DocumentFile,
)
async def generate_schedule_pdf(equipment_id: str) -> DocumentFile:
    """
    Автоматически генерирует график ППР/ТО в формате PDF,
    сохраняет его в каталог schedule/ агрегата и возвращает метаданные файла.
    """
    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    pdf_bytes = pdf_generator.generate_schedule_pdf(record)
    date_str = date.today().strftime("%Y%m%d")
    fn = f"schedule_{record.id}_{date_str}.pdf"
    doc = storage.save_pdf_document(record.id, "schedule", fn, pdf_bytes)
    return doc


@app.get("/api/equipment/{equipment_id}/budget-pdf")
async def get_equipment_budget_pdf(equipment_id: str) -> Response:
    """
    Выгружает в формате PDF бюджетную заявку на материалы и ТО по конкретному агрегату.
    """
    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    pdf_bytes = pdf_generator.generate_budget_pdf(
        [record],
        title=f"Бюджетная заявка на ТО: {record.name}",
    )
    headers = {
        "Content-Disposition": f"inline; filename=\"budget_{equipment_id}.pdf\"",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.get("/api/budget-report.pdf")
async def get_summary_budget_report_pdf() -> Response:
    """
    Выгружает сводную бюджетную заявку по всем агрегатам предприятия,
    требующим финансирования ТО и ТМЦ в ближайший горизонт.
    """
    records = storage.list_equipment()
    pdf_bytes = pdf_generator.generate_budget_pdf(
        records,
        title="Сводная бюджетная заявка на проведение ТО и закупку материалов",
    )
    headers = {
        "Content-Disposition": "inline; filename=\"budget_report_summary.pdf\"",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
