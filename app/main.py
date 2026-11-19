from __future__ import annotations

import logging
import mimetypes
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode

import httpx
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app import ad_auth, config, keycloak_auth, notifications, pdf_generator, qr_service, security_qr, storage
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
    при старте инициализирует демонстрационную базу (если не задан QR_DISABLE_AUTO_SEED=1).
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
    version="2.0.0",
    description="Локальный автономный узел технической документации, паспортизации, контроля ТО, закрытых QR и Keycloak OIDC",
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
    current_user = keycloak_auth.get_current_user(request)
    try:
        return templates.TemplateResponse(
            request=request,
            name="404.html",
            context={
                "request": request,
                "equipment_id": equipment_id,
                "message": "Оборудование не найдено",
                "current_user": current_user,
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
# Аутентификация Keycloak OIDC и сессии
# =============================================================================

@app.get("/auth/login", response_class=HTMLResponse)
async def auth_login_page(request: Request, target: str = "/") -> Response:
    """
    Страница входа: вход через официальный Keycloak Realm или быстрый выбор ролей.
    """
    return HTMLResponse(keycloak_auth.render_login_page(target_url=target))


@app.get("/auth/keycloak-redirect")
async def auth_keycloak_redirect(request: Request, target: str = "/") -> Response:
    """
    Перенаправляет пользователя на форму входа Keycloak (Authorization Code Flow).
    """
    host_header = request.headers.get("host") or f"{config.HOST}:{config.PORT}"
    scheme = request.url.scheme or "https"
    redirect_uri = f"{scheme}://{host_header}/auth/callback"

    state_data = f"{secrets.token_hex(8)}:{target}"
    endpoints = await keycloak_auth.get_keycloak_endpoints()

    params = {
        "client_id": config.KEYCLOAK_CLIENT_ID,
        "response_type": "code",
        "scope": "openid profile email roles",
        "redirect_uri": redirect_uri,
        "state": state_data,
    }
    kc_auth_url = f"{endpoints['auth']}?{urlencode(params)}"
    return RedirectResponse(url=kc_auth_url, status_code=status.HTTP_302_FOUND)


@app.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
) -> Response:
    """
    Callback от Keycloak после авторизации пользователя:
    обменивает code на токены, извлекает профиль и роли, устанавливает cookie сессии.
    """
    target = "/"
    if state and ":" in state:
        target = state.split(":", 1)[1] or "/"

    if error or not code:
        err_msg = error or "Авторизация Keycloak была отменена"
        return HTMLResponse(keycloak_auth.render_login_page(target_url=target, error=err_msg))

    host_header = request.headers.get("host") or f"{config.HOST}:{config.PORT}"
    scheme = request.url.scheme or "https"
    redirect_uri = f"{scheme}://{host_header}/auth/callback"

    endpoints = await keycloak_auth.get_keycloak_endpoints()

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            token_payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": config.KEYCLOAK_CLIENT_ID,
                "client_secret": config.KEYCLOAK_CLIENT_SECRET,
            }
            resp = await client.post(endpoints["token"], data=token_payload)

            if resp.status_code != 200:
                logger.warning("Ошибка обмена токена в Keycloak (%d): %s", resp.status_code, resp.text)
                return HTMLResponse(keycloak_auth.render_login_page(target_url=target, error="Ошибка проверки токена Keycloak"))

            tokens = resp.json()
            access_token = tokens.get("access_token", "")
            id_token = tokens.get("id_token", "")

            # Декодируем claims из JWT (без проверки подписи, так как получен напрямую по TLS/loopback от Keycloak)
            token_to_decode = id_token or access_token
            claims = jwt.decode(token_to_decode, options={"verify_signature": False})

            username = claims.get("preferred_username") or claims.get("sub", "user")
            name = claims.get("name") or claims.get("given_name") or username
            email = claims.get("email") or f"{username}@mind.local"
            sub = claims.get("sub", username)

            # Извлечение ролей
            realm_access = claims.get("realm_access", {})
            roles = realm_access.get("roles", [])
            if not roles:
                roles = ["operator"]

            user = keycloak_auth.UserProfile(
                sub=sub,
                username=username,
                name=name,
                email=email,
                roles=roles,
                role_label=keycloak_auth._make_role_label(roles),
                is_admin="admin" in roles,
                is_engineer="engineer" in roles or "admin" in roles,
            )

            jwt_session = keycloak_auth.create_session_jwt(user)
            response = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
            response.set_cookie(
                key=config.SESSION_COOKIE_NAME,
                value=jwt_session,
                max_age=86400 * 7,
                httponly=True,
                samesite="lax",
                secure=True,
            )
            return response
    except Exception as e:
        logger.exception("Исключение при обработке Keycloak callback: %s", e)
        return HTMLResponse(keycloak_auth.render_login_page(target_url=target, error=f"Ошибка соединения с Keycloak: {e}"))


@app.post("/auth/direct-login")
async def auth_direct_login(
    username: str = Form(...),
    password: str = Form(...),
    target: str = Form(default="/"),
) -> Response:
    """
    Прямой вход по логину/паролю:
    1. Через корпоративный Active Directory (AD / LDAP / LDAPS) АО «Интергаз Центральная Азия» (если включен).
    2. Либо через встроенные учётные записи Keycloak Realm (admin, engineer, operator).
    """
    u_raw = username.strip()
    u_lower = u_raw.lower()

    # 1. Проверка через корпоративный Active Directory
    if config.AD_ENABLED:
        ad_user_dict = ad_auth.authenticate_ad_user(u_raw, password)
        if ad_user_dict:
            user = keycloak_auth.UserProfile(
                sub=ad_user_dict["sub"],
                username=ad_user_dict["username"],
                name=ad_user_dict["name"],
                email=ad_user_dict["email"],
                roles=ad_user_dict["roles"],
                role_label=ad_user_dict["role_label"],
                is_admin=ad_user_dict["is_admin"],
                is_engineer=ad_user_dict["is_engineer"],
            )
            jwt_session = keycloak_auth.create_session_jwt(user)
            response = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
            response.set_cookie(
                key=config.SESSION_COOKIE_NAME,
                value=jwt_session,
                max_age=86400 * 7,
                httponly=True,
                samesite="lax",
                secure=True,
            )
            return response

    # 2. Проверка через встроенные учётные записи Keycloak Realm
    acc = keycloak_auth.BUILTIN_ACCOUNTS.get(u_lower)

    if not acc or acc["password"] != password:
        err_msg = "Неверный логин или пароль"
        if config.AD_ENABLED:
            err_msg += " (проверено в Active Directory и локальной базе)"
        return HTMLResponse(
            content=keycloak_auth.render_login_page(target_url=target, error=err_msg),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    user = keycloak_auth.UserProfile(
        sub=acc["sub"],
        username=acc["username"],
        name=acc["name"],
        email=acc["email"],
        roles=acc["roles"],
        role_label=keycloak_auth._make_role_label(acc["roles"]),
        is_admin="admin" in acc["roles"],
        is_engineer="engineer" in acc["roles"] or "admin" in acc["roles"],
    )

    jwt_session = keycloak_auth.create_session_jwt(user)
    response = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=jwt_session,
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    return response


@app.get("/api/auth/ad-status")
async def get_ad_status() -> dict[str, Any]:
    """
    Возвращает статус подключения и параметры интеграции с Active Directory
    (без раскрытия паролей и секретов).
    """
    status_info: dict[str, Any] = {
        "enabled": config.AD_ENABLED,
        "domain": config.AD_DOMAIN,
        "server": config.AD_SERVER,
        "base_dn": config.AD_BASE_DN,
        "users_ou": config.AD_USERS_OU,
        "use_ssl": config.AD_USE_SSL or config.AD_SERVER.startswith("ldaps://"),
        "role_groups": {
            "admin": config.AD_GROUP_ADMIN,
            "engineer": config.AD_GROUP_ENGINEER,
            "operator": config.AD_GROUP_OPERATOR,
        },
    }
    if config.AD_ENABLED:
        diag = ad_auth.test_ad_connection()
        status_info["connectivity"] = diag
    else:
        status_info["connectivity"] = {
            "success": False,
            "message": "Интеграция с Active Directory отключена (AD_ENABLED=false). Используется встроенный Keycloak realm.",
        }
    return status_info


@app.get("/auth/logout")
async def auth_logout(request: Request) -> Response:
    """
    Выход из учётной записи (очистка сессии).
    """
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=config.SESSION_COOKIE_NAME)
    return response


@app.get("/api/auth/me")
async def api_auth_me(request: Request) -> dict[str, Any]:
    """
    Возвращает профиль текущего аутентифицированного пользователя.
    """
    user = keycloak_auth.get_current_user(request)
    if not user:
        return {"authenticated": False, "user": None}
    return {
        "authenticated": True,
        "user": user.model_dump(),
    }


# =============================================================================
# HTML-маршруты (SPA и карточка оборудования)
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request) -> Response:
    """
    Главный экран (SPA):
    - кнопка запуска видеокамеры и закрытого QR-сканирования;
    - сводка уведомлений ТО и потребности в ЗИП;
    - реестр оборудования;
    - профиль пользователя Keycloak / Active Directory.
    """
    current_user = keycloak_auth.get_current_user(request)
    lan_ips = get_local_ipv4_addresses()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
            "port": config.PORT,
            "lan_ips": lan_ips,
            "current_user": current_user,
        },
    )


@app.get("/doc/{equipment_id}", response_class=HTMLResponse)
@app.get("/equipment/{equipment_id}", response_class=HTMLResponse)
async def equipment_page(request: Request, equipment_id: str) -> Response:
    """
    Карточка агрегата по ссылке из QR-кода:
    - 4 вкладки: Документы (PDF), Графики ТО и ЗИП, Фотоосмотр, Дефекты;
    - скачивание/печать защищённого QR-кода.
    """
    try:
        storage.validate_safe_name(equipment_id)
    except ValueError:
        return _render_not_found(request, equipment_id)

    record = storage.get_equipment(equipment_id)
    if not record:
        return _render_not_found(request, equipment_id)

    current_user = keycloak_auth.get_current_user(request)

    return templates.TemplateResponse(
        request=request,
        name="equipment.html",
        context={
            "request": request,
            "equipment_id": equipment_id,
            "equipment": record,
            "current_user": current_user,
        },
    )


# =============================================================================
# Защищённые QR-коды оборудования (только для камеры приложения)
# =============================================================================

class VerifyTokenPayload(BaseModel):
    token: str


@app.post("/api/verify-qr-token")
async def verify_qr_token(payload: VerifyTokenPayload, request: Request) -> dict[str, Any]:
    """
    Валидирует отсканированный QR-код (закрытый токен MINDEQUIP:v2:... или прямую ссылку).
    Камера приложения обращается к этому эндпоинту для мгновенной валидации и перехода к карточке.
    """
    current_user = keycloak_auth.get_current_user(request)

    scanned_text = payload.token.strip()

    # Проверяем закрытый протокол MINDEQUIP:v2:
    if scanned_text.startswith("MINDEQUIP:"):
        result = security_qr.verify_secure_qr_token(scanned_text)
        result["user"] = current_user.username if current_user else "anonymous"
        return result

    # Проверка на обычные ссылки (обратная совместимость)
    match_doc = re.search(r"/doc/([a-zA-Z0-9_\-]+)", scanned_text)
    if match_doc:
        eq_id = match_doc.group(1)
        record = storage.get_equipment(eq_id)
        if record:
            return {
                "is_secure_qr": False,
                "valid": True,
                "equipment_id": eq_id,
                "equipment_name": record.name,
                "inventory_number": record.inventory_number,
                "card_url": f"/doc/{eq_id}",
                "error": None,
            }

    # Проверка, если отсканирован просто идентификатор агрегата
    record = storage.get_equipment(scanned_text)
    if record:
        return {
            "is_secure_qr": False,
            "valid": True,
            "equipment_id": record.id,
            "equipment_name": record.name,
            "inventory_number": record.inventory_number,
            "card_url": f"/doc/{record.id}",
            "error": None,
        }

    return {
        "is_secure_qr": False,
        "valid": False,
        "error": "QR-код не соответствует оборудованию в базе",
        "equipment_id": None,
        "card_url": None,
    }


@app.get("/api/equipment/{equipment_id}/secure-qr")
async def get_secure_qr_png(equipment_id: str) -> Response:
    """
    Генерирует PNG защищённого стикера QR-кода оборудования.
    В этот QR кодируется закрытый крипто-токен MINDEQUIP:v2:<id>:<token>,
    который не открывается обычными сторонними камерами и доступен только приложению.
    """
    try:
        storage.validate_safe_name(equipment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    png_bytes = security_qr.generate_secure_qr_png(equipment_id)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache",
            "Content-Disposition": f"inline; filename=\"secure_qr_{equipment_id}.png\"",
        },
    )


@app.post("/api/equipment/{equipment_id}/rotate-qr")
async def rotate_equipment_qr(equipment_id: str, request: Request) -> dict[str, Any]:
    """
    Перевыпускает защищённый криптографический QR-токен агрегата.
    Требует учётную запись с ролью admin или engineer.
    """
    current_user = keycloak_auth.get_current_user(request)
    if not current_user or not current_user.is_engineer:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуются права инженера или администратора")

    try:
        storage.validate_safe_name(equipment_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    new_token = security_qr.rotate_secure_token(equipment_id)
    new_payload = security_qr.generate_secure_qr_payload(equipment_id)

    return {
        "status": "ok",
        "equipment_id": equipment_id,
        "token": new_token,
        "payload": new_payload,
        "secure_qr_url": f"/api/equipment/{equipment_id}/secure-qr",
    }


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

    if inline == 1:
        disposition_type = "inline"
    elif download == 1:
        disposition_type = "attachment"
    elif category == "photos":
        disposition_type = "inline"
    else:
        disposition_type = "attachment"

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
    Проверка работоспособности сервера и интеграции Keycloak.
    """
    kc_online = await keycloak_auth.is_keycloak_available()
    return {
        "status": "ok",
        "host": config.HOST,
        "port": config.PORT,
        "keycloak_url": config.KEYCLOAK_URL,
        "keycloak_realm": config.KEYCLOAK_REALM,
        "keycloak_online": kc_online,
    }


@app.get("/api/network-info")
async def network_info() -> dict[str, Any]:
    """
    Возвращает информацию о порте 8443 и доступных локальных IPv4-адресах для подключения по Wi-Fi.
    """
    lan_ips = get_local_ipv4_addresses()
    lan_urls = [f"https://{ip}:{config.PORT}" for ip in lan_ips]
    primary_url = lan_urls[0] if lan_urls else f"https://127.0.0.1:{config.PORT}"
    kc_online = await keycloak_auth.is_keycloak_available()
    return {
        "host": config.HOST,
        "port": config.PORT,
        "lan_ips": lan_ips,
        "interfaces": lan_ips,
        "lan_urls": lan_urls,
        "primary_url": primary_url,
        "keycloak_online": kc_online,
    }


@app.get("/404", response_class=HTMLResponse)
async def not_found_page(request: Request) -> Response:
    return _render_not_found(request, "—")


@app.get("/api/overview")
async def overview() -> dict[str, Any]:
    """
    Сводка по оборудованию, активные предупреждения о сроках ТО и дефиците ЗИП.
    """
    return notifications.build_overview()


# =============================================================================
# API Оборудования (Реестр, карточка, QR)
# =============================================================================

def _build_full_equipment_card(record: EquipmentRecord) -> dict[str, Any]:
    documents = storage.list_documents(record.id)
    evaluation = notifications.evaluate_equipment(record, docs=documents)
    secure_payload = security_qr.generate_secure_qr_payload(record.id)
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
        "secure_payload": secure_payload,
        "secure_qr_url": f"/api/equipment/{record.id}/secure-qr",
        "card_path": f"/doc/{record.id}",
    }


@app.post("/api/equipment", status_code=status.HTTP_201_CREATED)
async def create_equipment(
    payload: EquipmentCreateInput,
    auto_passport: bool = Query(default=True),
    request: Request = None,
) -> dict[str, Any]:
    """
    Добавляет новую единицу оборудования в локальную базу.
    При auto_passport=True автоматически генерирует стартовый паспорт PDF.
    Возвращает статус 201 и полную карточку оборудования.
    """
    try:
        record = storage.create_equipment(payload)
        security_qr.get_or_create_secure_token(record.id)
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
    Возвращает полные данные карточки оборудования, локальные документы и статус ЗИП.
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
    Генерирует стандартный QR-код со ссылкой на карточку агрегата.
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
    request: Request = None,
) -> PhotoInspection:
    """
    Загружает фотографию технического состояния агрегата со смартфона:
    валидирует формат изображения, сохраняет в photos/, обновляет статус оборудования
    и добавляет запись в ленту осмотров.
    """
    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    current_user = keycloak_auth.get_current_user(request) if request else None
    author_note = f" [{current_user.name}]" if current_user else ""
    full_comment = f"{comment}{author_note}".strip()

    content = await file.read()
    try:
        photo = storage.save_photo_inspection(
            equipment_id=equipment_id,
            filename=file.filename or "inspection.jpg",
            content=content,
            condition=condition,
            node=node,
            comment=full_comment,
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
    request: Request = None,
) -> dict[str, Any]:
    """
    Фиксирует выполнение ТО:
    - пересчитывает дату следующего ТО;
    - обновляет остатки ТМЦ на складе;
    - вносит запись в историю ТО;
    - возвращает обновлённую карточку оборудования.
    """
    current_user = keycloak_auth.get_current_user(request) if request else None
    if current_user and not payload.performer:
        payload.performer = f"{current_user.name} ({current_user.username})"

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
# API Автогенерации PDF (Дефектные ведомости, графики ТО, ведомости ЗИП)
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
    Выгружает в формате PDF ведомость потребности в ЗИП и график ТО по конкретному агрегату.
    """
    record = storage.get_equipment(equipment_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оборудование не найдено")

    pdf_bytes = pdf_generator.generate_budget_pdf(
        [record],
        title=f"Ведомость потребности в ЗИП и график ТО: {record.name}",
    )
    headers = {
        "Content-Disposition": f"inline; filename=\"zip_plan_{equipment_id}.pdf\"",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)


@app.get("/api/budget-report.pdf")
async def get_summary_budget_report_pdf() -> Response:
    """
    Выгружает сводный график регламентных работ и ведомость потребности в ЗИП по всем агрегатам предприятия.
    """
    records = storage.list_equipment()
    pdf_bytes = pdf_generator.generate_budget_pdf(
        records,
        title="Сводный график регламентных работ и ведомость потребности в ЗИП",
    )
    headers = {
        "Content-Disposition": "inline; filename=\"zip_schedule_summary.pdf\"",
        "X-Content-Type-Options": "nosniff",
    }
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
