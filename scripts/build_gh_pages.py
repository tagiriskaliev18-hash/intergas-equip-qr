"""
Build static GitHub Pages bundle into ./docs/
Produces a 100% live, interactive static version of the Intergas Central Asia
Equipment Documentation & Maintenance QR platform (zero monetary sums, closed QR,
Keycloak role-based demo auth, real downloadable PDFs and inspection photos).
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from jinja2 import Environment, FileSystemLoader

from app import pdf_generator, security_qr, storage
from app.seed_demo import seed_demo_data_if_empty

DOCS_OUT = ROOT / "docs"


def build_login_html() -> str:
    return """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <title>Вход в систему — Интергаз Центральная Азия · Keycloak</title>
  <link rel="stylesheet" href="static/css/styles.css">
  <style>
    .login-wrapper {
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      background-color: var(--bg);
    }
    .login-card {
      width: 100%;
      max-width: 440px;
      background: var(--panel);
      border: 1px solid var(--hairline-hover);
      border-radius: var(--radius-lg);
      padding: 28px 24px;
      box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
    }
    .login-logo {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 20px;
      justify-content: center;
    }
    .login-title {
      font-size: 19px;
      font-weight: 700;
      color: var(--text-primary);
      text-align: center;
      margin-bottom: 6px;
    }
    .login-desc {
      font-size: 13.5px;
      color: var(--text-secondary);
      text-align: center;
      margin-bottom: 22px;
      line-height: 1.45;
    }
    .login-error-badge {
      display: none;
      background: var(--state-crit-bg);
      border: 1px solid var(--state-crit-border);
      color: var(--state-crit);
      border-radius: var(--radius-sm);
      padding: 10px 12px;
      font-size: 13.5px;
      margin-bottom: 16px;
      text-align: center;
    }
    .divider-or {
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--text-muted);
      font-size: 12px;
      margin: 20px 0;
    }
    .divider-or::before, .divider-or::after {
      content: '';
      flex: 1;
      height: 1px;
      background: var(--hairline);
    }
    .quick-account-btn {
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
      cursor: pointer;
      transition: background-color var(--transition-fast), border-color var(--transition-fast);
    }
    .quick-account-btn:hover {
      background: var(--panel-elevated);
      border-color: var(--hairline-hover);
    }
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
          <span>Интергаз · Keycloak · HTTPS</span>
        </div>
      </div>

      <h1 class="login-title">Интергаз Центральная Азия</h1>
      <p class="login-desc">Единая база документации, паспортизации и ТО оборудования ЛПУ, ГРС и КС по защищённым QR-кодам.</p>

      <div class="login-error-badge" id="login-error"></div>

      <form id="login-form">
        <div class="form-group">
          <label class="form-label" for="inp-username">Логин (Keycloak Realm: mind-equip)</label>
          <input type="text" class="form-input mono" id="inp-username" required placeholder="admin / engineer / operator" autocomplete="username">
        </div>
        <div class="form-group">
          <label class="form-label" for="inp-password">Пароль</label>
          <input type="password" class="form-input mono" id="inp-password" required placeholder="••••••••" autocomplete="current-password">
        </div>
        <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 6px;">
          Войти в систему
        </button>
      </form>

      <div class="divider-or">Быстрый вход под ролью (Keycloak Realm)</div>

      <button type="button" class="quick-account-btn" data-user="admin" data-pass="admin123">
        <div>
          <div style="font-weight: 600;">Главный механик (admin)</div>
          <div style="font-size: 12px; color: var(--text-muted);">Полный доступ · перевыпуск QR · ТО и ЗИП</div>
        </div>
        <span class="mono" style="font-size: 11px; color: var(--accent-cyan);">admin123</span>
      </button>

      <button type="button" class="quick-account-btn" data-user="engineer" data-pass="engineer123">
        <div>
          <div style="font-weight: 600;">Инженер ТО и диагностики (engineer)</div>
          <div style="font-size: 12px; color: var(--text-muted);">Графики ТО · дефекты · перевыпуск QR</div>
        </div>
        <span class="mono" style="font-size: 11px; color: var(--state-good);">engineer123</span>
      </button>

      <button type="button" class="quick-account-btn" data-user="operator" data-pass="operator123">
        <div>
          <div style="font-weight: 600;">Дежурный оператор КС/ГРС (operator)</div>
          <div style="font-size: 12px; color: var(--text-muted);">Сканер QR · просмотр PDF-паспортов</div>
        </div>
        <span class="mono" style="font-size: 11px; color: var(--text-secondary);">operator123</span>
      </button>

      <div style="text-align: center; margin-top: 16px;">
        <a href="index.html" style="font-size: 13px; color: var(--text-secondary);">← Вернуться к сканеру без входа</a>
      </div>
    </div>
  </div>

  <script src="static/js/gh-pages-adapter.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      const form = document.getElementById('login-form');
      const errBox = document.getElementById('login-error');
      const params = new URLSearchParams(window.location.search);
      const target = params.get('target') || 'index.html';

      function doLogin(u, p) {
        const profile = window.ICAAuth.loginUser(u, p);
        if (!profile) {
          errBox.textContent = 'Неверный логин или пароль. Используйте admin/admin123, engineer/engineer123 или operator/operator123.';
          errBox.style.display = 'block';
          return;
        }
        window.location.href = target;
      }

      form.addEventListener('submit', (e) => {
        e.preventDefault();
        doLogin(document.getElementById('inp-username').value, document.getElementById('inp-password').value);
      });

      document.querySelectorAll('.quick-account-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          doLogin(btn.getAttribute('data-user'), btn.getAttribute('data-pass'));
        });
      });
    });
  </script>
</body>
</html>
"""


def rewrite_static_js(content: str) -> str:
    # Rewrite navigation links to static relative GitHub Pages paths
    content = content.replace(
        "`/doc/${encodeURIComponent(",
        "`equipment.html?id=${encodeURIComponent(",
    )
    content = content.replace(
        "href=\"/doc/${encodeURIComponent(",
        "href=\"equipment.html?id=${encodeURIComponent(",
    )
    content = content.replace(
        "window.location.href = '/404';",
        "window.location.href = '404.html';",
    )
    content = content.replace(
        "`/api/equipment/${encodeURIComponent(equipmentId)}/budget-pdf`",
        "`reports/plan_${encodeURIComponent(equipmentId)}.pdf`",
    )
    content = content.replace(
        "`/api/equipment/${encodeURIComponent(equipmentId)}/secure-qr`",
        "`qr/${encodeURIComponent(equipmentId)}.png`",
    )
    content = content.replace(
        "/api/equipment/${encodeURIComponent(item.id)}/qr?origin=${encodeURIComponent(window.location.origin)}",
        "qr/${encodeURIComponent(item.id)}.png",
    )
    return content


def main() -> None:
    seed_demo_data_if_empty(force_reseed=False)
    records = storage.list_equipment()
    if not records:
        raise RuntimeError("No equipment records found to export.")

    if DOCS_OUT.exists():
        shutil.rmtree(DOCS_OUT)
    DOCS_OUT.mkdir(parents=True, exist_ok=True)
    (DOCS_OUT / ".nojekyll").write_text("", encoding="utf-8")

    # 1. Copy static assets
    shutil.copytree(ROOT / "static", DOCS_OUT / "static")
    shutil.copy2(
        ROOT / "scripts" / "gh_pages_adapter.js",
        DOCS_OUT / "static" / "js" / "gh-pages-adapter.js",
    )

    # Adapt JS files for static GitHub Pages routing
    for js_name in ("scanner.js", "equipment.js"):
        js_path = DOCS_OUT / "static" / "js" / js_name
        js_path.write_text(rewrite_static_js(js_path.read_text(encoding="utf-8")), encoding="utf-8")

    # 2. Export documents, photos, QR stickers, PDFs, and initial state JSON
    reports_dir = DOCS_OUT / "reports"
    qr_dir = DOCS_OUT / "qr"
    data_dir = DOCS_OUT / "data"
    docs_files_dir = DOCS_OUT / "documents"
    reports_dir.mkdir(parents=True, exist_ok=True)
    qr_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    docs_files_dir.mkdir(parents=True, exist_ok=True)

    # Summary Plan PDF (zero money sums)
    summary_pdf = pdf_generator.generate_budget_pdf(records)
    (reports_dir / "summary_plan.pdf").write_bytes(summary_pdf)

    exported_equipment = []
    exported_documents: dict[str, dict[str, list[dict]]] = {}
    exported_qr_tokens: dict[str, str] = {}

    for rec in records:
        eq_dict = rec.model_dump()

        # Copy all equipment documents & photos into docs/documents/<id>/
        src_eq_dir = storage.get_docs_root() / rec.id
        dst_eq_dir = docs_files_dir / rec.id
        if src_eq_dir.exists():
            shutil.copytree(src_eq_dir, dst_eq_dir)

        # Rewrite photo URLs to relative paths
        for photo in eq_dict.get("photos", []):
            fn = photo.get("filename", "")
            if fn:
                photo["url"] = f"documents/{rec.id}/photos/{fn}"

        # Rewrite document download URLs to relative paths
        docs_by_cat = storage.list_documents(rec.id)
        exported_documents[rec.id] = {}
        for cat, items in docs_by_cat.items():
            exported_documents[rec.id][cat] = []
            for d in items:
                d_dict = d.model_dump()
                d_dict["download_url"] = f"documents/{rec.id}/{cat}/{d.filename}"
                exported_documents[rec.id][cat].append(d_dict)

        # Generate per-equipment plan PDF (zero money sums)
        plan_pdf = pdf_generator.generate_schedule_pdf(rec)
        (reports_dir / f"plan_{rec.id}.pdf").write_bytes(plan_pdf)

        # Generate closed proprietary QR sticker PNG & record token
        token = security_qr.get_or_create_secure_token(rec.id)
        exported_qr_tokens[rec.id] = token
        qr_png = security_qr.generate_secure_qr_png(rec.id)
        (qr_dir / f"{rec.id}.png").write_bytes(qr_png)

        exported_equipment.append(eq_dict)

    initial_state = {
        "equipment": exported_equipment,
        "documents": exported_documents,
        "qr_tokens": exported_qr_tokens,
    }
    (data_dir / "initial-state.json").write_text(
        json.dumps(initial_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 3. Render HTML pages from Jinja2 templates
    env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))

    # index.html
    index_html = env.get_template("index.html").render(
        current_user=None,
        port="HTTPS",
    )
    index_html = index_html.replace('href="/static/', 'href="static/')
    index_html = index_html.replace('src="/static/', 'src="static/')
    index_html = index_html.replace('href="/"', 'href="index.html"')
    index_html = index_html.replace('href="/api/budget-report.pdf"', 'href="reports/summary_plan.pdf"')
    index_html = index_html.replace('href="/auth/login"', 'href="login.html"')
    index_html = index_html.replace('<span>TLS · 8443</span>', '<span>TLS · HTTPS</span>')
    index_html = index_html.replace(
        '<div class="user-auth-wrap">',
        '<div class="user-auth-wrap" id="gh-auth-header">',
    )
    index_html = index_html.replace(
        '<script src="static/js/scanner.js"></script>',
        '<script src="static/js/gh-pages-adapter.js"></script>\n  <script src="static/js/scanner.js"></script>',
    )
    (DOCS_OUT / "index.html").write_text(index_html, encoding="utf-8")

    # equipment.html
    first_id = records[0].id
    equip_html = env.get_template("equipment.html").render(
        current_user=None,
        equipment_id=first_id,
        equipment_name="Загрузка агрегата...",
        inventory_number="...",
        port="HTTPS",
    )
    equip_html = equip_html.replace('href="/static/', 'href="static/')
    equip_html = equip_html.replace('src="/static/', 'src="static/')
    equip_html = equip_html.replace('href="/"', 'href="index.html"')
    equip_html = equip_html.replace('href="/auth/login"', 'href="login.html"')
    equip_html = equip_html.replace('<span>TLS · 8443</span>', '<span>TLS · HTTPS</span>')
    equip_html = equip_html.replace(
        '<div class="user-auth-wrap">',
        '<div class="user-auth-wrap" id="gh-auth-header">',
    )
    equip_html = equip_html.replace(
        f'src="/api/equipment/{first_id}/secure-qr"',
        f'src="qr/{first_id}.png"',
    )
    equip_html = equip_html.replace(
        f'href="/api/equipment/{first_id}/secure-qr"',
        f'href="qr/{first_id}.png"',
    )
    # Always include rotate button in static DOM (adapter toggles visibility by role)
    rotate_btn_html = (
        '<button type="button" class="btn btn-warn btn-sm" id="btn-rotate-qr-token" style="display: none;" '
        'title="Сгенерировать новый ключ. Прежний распечатанный QR-код перестанет работать.">'
        '🔄 Перевыпустить токен</button>'
    )
    equip_html = equip_html.replace(
        'Печать\n          </button>',
        'Печать\n          </button>\n          ' + rotate_btn_html,
    )
    # Inject synchronous equipment_id resolver before equipment.js runs
    id_bootstrap = f"""<script>
    (function() {{
      var params = new URLSearchParams(window.location.search);
      var eqId = params.get('id') || '{first_id}';
      var c = document.getElementById('equipment-container');
      if (c) c.setAttribute('data-equipment-id', eqId);
      var img = document.getElementById('qr-modal-image');
      if (img) img.src = 'qr/' + encodeURIComponent(eqId) + '.png';
      var dl = document.getElementById('qr-modal-download-link');
      if (dl) {{
        dl.href = 'qr/' + encodeURIComponent(eqId) + '.png';
        dl.setAttribute('download', 'secure_qr_' + eqId + '.png');
      }}
    }})();
  </script>
  <script src="static/js/gh-pages-adapter.js"></script>
  <script src="static/js/equipment.js"></script>"""
    equip_html = equip_html.replace(
        '<script src="static/js/equipment.js"></script>',
        id_bootstrap,
    )
    (DOCS_OUT / "equipment.html").write_text(equip_html, encoding="utf-8")

    # login.html
    (DOCS_OUT / "login.html").write_text(build_login_html(), encoding="utf-8")

    # 404.html
    not_found_html = env.get_template("404.html").render()
    not_found_html = not_found_html.replace('href="/static/', 'href="static/')
    not_found_html = not_found_html.replace('href="/"', 'href="index.html"')
    (DOCS_OUT / "404.html").write_text(not_found_html, encoding="utf-8")

    print(f"GitHub Pages bundle built successfully in {DOCS_OUT} ({len(records)} assets exported)!")


if __name__ == "__main__":
    main()
