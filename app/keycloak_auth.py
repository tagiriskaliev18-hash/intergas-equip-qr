from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Optional
from urllib.parse import quote_plus, urlencode

import httpx
import jwt
from fastapi import Cookie, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app import config

logger = logging.getLogger(__name__)

# Роли и их понятные русские наименования
ROLE_TITLES = {
    "admin": "Главный механик / Администратор",
    "engineer": "Инженер ТО / Механик",
    "operator": "Оператор / Наблюдатель",
}

# Встроенные тестовые учётные записи (полностью дублируют realm-export.json Keycloak)
BUILTIN_ACCOUNTS = {
    "admin": {
        "password": "admin123",
        "username": "admin",
        "name": "Иван Иванов",
        "email": "admin@mind.local",
        "roles": ["admin", "engineer"],
        "sub": "user-admin-01",
    },
    "engineer": {
        "password": "engineer123",
        "username": "engineer",
        "name": "Петр Петров",
        "email": "engineer@mind.local",
        "roles": ["engineer"],
        "sub": "user-engineer-02",
    },
    "operator": {
        "password": "operator123",
        "username": "operator",
        "name": "Сергей Сидоров",
        "email": "operator@mind.local",
        "roles": ["operator"],
        "sub": "user-operator-03",
    },
}


class UserProfile(BaseModel):
    sub: str
    username: str
    name: str
    email: str
    roles: list[str]
    role_label: str
    is_admin: bool = False
    is_engineer: bool = False


def _make_role_label(roles: list[str]) -> str:
    for r in ("admin", "engineer", "operator"):
        if r in roles:
            return ROLE_TITLES.get(r, r)
    return "Сотрудник"


def create_session_jwt(user: UserProfile) -> str:
    payload = {
        "sub": user.sub,
        "username": user.username,
        "name": user.name,
        "email": user.email,
        "roles": user.roles,
        "role_label": user.role_label,
        "is_admin": user.is_admin,
        "is_engineer": user.is_engineer,
        "iat": int(time.time()),
        "exp": int(time.time()) + 86400 * 7,  # 7 суток
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_session_jwt(token: str) -> Optional[UserProfile]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
        return UserProfile(
            sub=payload.get("sub", ""),
            username=payload.get("username", ""),
            name=payload.get("name", payload.get("username", "")),
            email=payload.get("email", ""),
            roles=payload.get("roles", []),
            role_label=payload.get("role_label", "Сотрудник"),
            is_admin="admin" in payload.get("roles", []),
            is_engineer="engineer" in payload.get("roles", []) or "admin" in payload.get("roles", []),
        )
    except Exception:
        return None


def get_current_user(request: Request) -> Optional[UserProfile]:
    """
    Извлекает аутентифицированного пользователя из сессионного cookie или Bearer заголовка.
    """
    # 1. Проверка Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        user = decode_session_jwt(auth_header[7:].strip())
        if user:
            return user

    # 2. Проверка cookie
    cookie_token = request.cookies.get(config.SESSION_COOKIE_NAME)
    if cookie_token:
        return decode_session_jwt(cookie_token)

    return None


async def is_keycloak_available() -> bool:
    """
    Проверяет доступность сервера Keycloak.
    """
    url = f"{config.KEYCLOAK_URL}/realms/{config.KEYCLOAK_REALM}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            resp = await client.get(url)
            return resp.status_code == 200
    except Exception:
        return False


async def get_keycloak_endpoints() -> dict[str, str]:
    """
    Загружает OIDC endpoints из Keycloak discovery.
    """
    url = f"{config.KEYCLOAK_URL}/realms/{config.KEYCLOAK_REALM}/.well-known/openid-configuration"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "auth": data.get("authorization_endpoint"),
                    "token": data.get("token_endpoint"),
                    "userinfo": data.get("userinfo_endpoint"),
                    "logout": data.get("end_session_endpoint"),
                }
    except Exception as e:
        logger.warning("Ошибка получения OIDC discovery Keycloak: %s", e)

    base = f"{config.KEYCLOAK_URL}/realms/{config.KEYCLOAK_REALM}/protocol/openid-connect"
    return {
        "auth": f"{base}/auth",
        "token": f"{base}/token",
        "userinfo": f"{base}/userinfo",
        "logout": f"{base}/logout",
    }


def render_login_page(target_url: str = "/", error: str = "") -> str:
    """
    Генерирует приборную форму входа Mind Equip с выбором
    входа через официальный Keycloak или быстрым выбором ролей.
    """
    err_html = f"<div class='login-error-badge'>{error}</div>" if error else ""
    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>Вход в систему — Mind Equip & Keycloak</title>
  <link rel="stylesheet" href="/static/css/styles.css">
  <style>
    .login-wrapper {{
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      background-color: var(--bg);
    }}
    .login-card {{
      width: 100%;
      max-width: 440px;
      background: var(--panel);
      border: 1px solid var(--hairline-hover);
      border-radius: var(--radius-lg);
      padding: 28px 24px;
      box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
    }}
    .login-logo {{
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
      justify-content: center;
    }}
    .login-title {{
      font-size: 19px;
      font-weight: 700;
      color: var(--text-primary);
      text-align: center;
      margin-bottom: 6px;
    }}
    .login-desc {{
      font-size: 13.5px;
      color: var(--text-secondary);
      text-align: center;
      margin-bottom: 22px;
      line-height: 1.45;
    }}
    .login-error-badge {{
      background: var(--state-crit-bg);
      border: 1px solid var(--state-crit-border);
      color: var(--state-crit);
      border-radius: var(--radius-sm);
      padding: 10px 12px;
      font-size: 13.5px;
      margin-bottom: 16px;
      text-align: center;
    }}
    .btn-keycloak-sso {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      height: 52px;
      background: #4B3BFF;
      color: #FFFFFF;
      font-weight: 600;
      font-size: 15px;
      border-radius: var(--radius-sm);
      border: 1px solid rgba(255, 255, 255, 0.18);
      box-shadow: 0 4px 16px rgba(75, 59, 255, 0.35);
      margin-bottom: 20px;
    }}
    .divider-or {{
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--text-muted);
      font-size: 12px;
      margin-bottom: 20px;
    }}
    .divider-or::before, .divider-or::after {{
      content: '';
      flex: 1;
      height: 1px;
      background: var(--hairline);
    }}
    .quick-account-btn {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: 100%;
      padding: 10px 14px;
      background: var(--panel-sub);
      border: 1px solid var(--hairline);
      border-radius: var(--radius-sm);
      color: var(--text-primary);
      font-size: 13.5px;
      margin-bottom: 8px;
      text-align: left;
      transition: background-color var(--transition-fast), border-color var(--transition-fast);
    }}
    .quick-account-btn:hover {{
      background: var(--panel-elevated);
      border-color: var(--hairline-hover);
    }}
  </style>
</head>
<body>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="login-logo">
        <div class="mind-badge" style="width: 32px; height: 32px;">
          <span class="mind-badge-glyph" style="font-size: 13px; letter-spacing: 0;">ICA</span>
        </div>
        <div class="tls-badge">
          <span class="cyan-dot"></span>
          <span>Интергаз · Keycloak · {config.PORT}</span>
        </div>
      </div>

      <h1 class="login-title">Интергаз Центральная Азия</h1>
      <p class="login-desc">Единая база документации, паспортизации и ТО оборудования ЛПУ, ГРС и КС по защищённым QR-кодам.</p>

      {err_html}

      <!-- Primary SSO Keycloak Button -->
      <a href="/auth/keycloak-redirect?target={quote_plus(target_url)}" class="btn-keycloak-sso">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
          <polyline points="10 17 15 12 10 7"/>
          <line x1="15" y1="12" x2="3" y2="12"/>
        </svg>
        Войти через сервер Keycloak
      </a>

      <div class="divider-or">Или быстрый вход под ролью (Keycloak Realm)</div>

      <!-- Quick Role Selection Forms -->
      <form action="/auth/direct-login" method="POST">
        <input type="hidden" name="target" value="{target_url}">
        <input type="hidden" name="username" value="admin">
        <input type="hidden" name="password" value="admin123">
        <button type="submit" class="quick-account-btn">
          <div>
            <strong>admin</strong> · Иван Иванов
            <div style="font-size: 12px; color: var(--text-secondary);">Главный механик (полный доступ)</div>
          </div>
          <span class="status-chip good" style="font-size: 11px;">Admin</span>
        </button>
      </form>

      <form action="/auth/direct-login" method="POST">
        <input type="hidden" name="target" value="{target_url}">
        <input type="hidden" name="username" value="engineer">
        <input type="hidden" name="password" value="engineer123">
        <button type="submit" class="quick-account-btn">
          <div>
            <strong>engineer</strong> · Петр Петров
            <div style="font-size: 12px; color: var(--text-secondary);">Сменный инженер (ТО, осмотры, дефекты)</div>
          </div>
          <span class="status-chip attention" style="font-size: 11px;">Engineer</span>
        </button>
      </form>

      <form action="/auth/direct-login" method="POST">
        <input type="hidden" name="target" value="{target_url}">
        <input type="hidden" name="username" value="operator">
        <input type="hidden" name="password" value="operator123">
        <button type="submit" class="quick-account-btn">
          <div>
            <strong>operator</strong> · Сергей Сидоров
            <div style="font-size: 12px; color: var(--text-secondary);">Оператор оборудования (просмотр паспортов)</div>
          </div>
          <span class="status-chip" style="font-size: 11px; background: rgba(255,255,255,0.06); color: var(--text-secondary);">Viewer</span>
        </button>
      </form>

      <!-- Standard credentials form -->
      <form action="/auth/direct-login" method="POST" style="margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--hairline);">
        <input type="hidden" name="target" value="{target_url}">
        <div class="form-group" style="margin-bottom: 8px;">
          <input type="text" name="username" class="form-input" placeholder="Логин (например, admin)" required style="font-size: 14px; padding: 8px 10px;">
        </div>
        <div class="form-group" style="margin-bottom: 12px;">
          <input type="password" name="password" class="form-input" placeholder="Пароль" required style="font-size: 14px; padding: 8px 10px;">
        </div>
        <button type="submit" class="btn btn-secondary btn-sm" style="width: 100%;">
          Войти по логину и паролю
        </button>
      </form>

    </div>
  </div>
</body>
</html>"""
