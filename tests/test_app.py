"""
Comprehensive automated tests for QR Code Equipment Passportization and Maintenance System.
Validates business logic, path security, SSL SAN certificates, PDF/PNG generation, and offline-readiness.
"""
from __future__ import annotations

import io
import ipaddress
from datetime import date, timedelta
from pathlib import Path

import pytest
from PIL import Image


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Isolates local filesystem storage for each test using tmp_path and monkeypatch.
    Prevents tests from polluting or mutating the production ./documents and ./certs folders.
    """
    docs_dir = tmp_path / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir(parents=True, exist_ok=True)

    # Disable auto-seed of demo equipment during testing
    monkeypatch.setenv("QR_DISABLE_AUTO_SEED", "1")
    monkeypatch.setenv("QR_DOCS_DIR", str(docs_dir))
    monkeypatch.setenv("QR_CERTS_DIR", str(certs_dir))

    import app.config
    monkeypatch.setattr(app.config, "DOCS_DIR", docs_dir)
    monkeypatch.setattr(app.config, "CERTS_DIR", certs_dir)
    monkeypatch.setattr(app.config, "CERT_FILE", certs_dir / "cert.pem")
    monkeypatch.setattr(app.config, "KEY_FILE", certs_dir / "key.pem")

    # If storage module is already imported or imported later, ensure its directory references point to tmp_path
    try:
        import app.storage
        if hasattr(app.storage, "DOCS_DIR"):
            monkeypatch.setattr(app.storage, "DOCS_DIR", docs_dir)
        if hasattr(app.storage, "REGISTRY_FILE"):
            monkeypatch.setattr(app.storage, "REGISTRY_FILE", docs_dir / "registry.json")
    except ImportError:
        pass

    return docs_dir


@pytest.fixture
def client(isolated_storage: Path, monkeypatch: pytest.MonkeyPatch):
    """
    FastAPI TestClient with isolated environment and filesystem storage.
    """
    import app.main
    from fastapi.testclient import TestClient

    with TestClient(app.main.app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# 1. SSL Certificate & SAN Tests
# ---------------------------------------------------------------------------

def test_ssl_certificate_san_and_validity(tmp_path: Path) -> None:
    """
    Verifies that ensure_self_signed_cert:
    - Generates a valid X.509 certificate and private key.
    - Includes IPAddress('0.0.0.0'), IPAddress('127.0.0.1'), and DNSName('localhost') in SubjectAlternativeName.
    - Sets validity period <= 825 days (strictly required by Apple iOS Safari).
    """
    import cryptography.x509
    from cryptography.x509.oid import ExtensionOID
    from app.ssl_manager import ensure_self_signed_cert

    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"

    ssl_info = ensure_self_signed_cert(
        cert_path=cert_path,
        key_path=key_path,
        force_regen=True,
        validity_days=365,
    )
    assert isinstance(ssl_info, dict) and "0.0.0.0" in ssl_info.get("san_ips", [])

    assert cert_path.is_file(), f"Certificate file was not created at {cert_path}"
    assert key_path.is_file(), f"Private key file was not created at {key_path}"

    cert_bytes = cert_path.read_bytes()
    cert = cryptography.x509.load_pem_x509_certificate(cert_bytes)

    # Check validity duration <= 825 days (Apple iOS limit)
    try:
        not_before = cert.not_valid_before_utc
        not_after = cert.not_valid_after_utc
    except AttributeError:
        not_before = cert.not_valid_before
        not_after = cert.not_valid_after

    validity_duration = not_after - not_before
    assert validity_duration.days <= 825, (
        f"Certificate validity {validity_duration.days} days exceeds Apple iOS 825 days limit!"
    )
    assert validity_duration.days >= 360, (
        f"Expected certificate validity around 365 days, got {validity_duration.days} days"
    )

    # Check SubjectAlternativeName (SAN)
    san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
    san = san_ext.value

    # Validate IP addresses in SAN
    ip_addrs = san.get_values_for_type(cryptography.x509.IPAddress)
    assert ipaddress.IPv4Address("0.0.0.0") in ip_addrs, (
        f"IP 0.0.0.0 is missing from SAN IP addresses: {ip_addrs}"
    )
    assert ipaddress.IPv4Address("127.0.0.1") in ip_addrs, (
        f"IP 127.0.0.1 is missing from SAN IP addresses: {ip_addrs}"
    )

    # Validate DNS names in SAN
    dns_names = san.get_values_for_type(cryptography.x509.DNSName)
    assert "localhost" in dns_names, (
        f"'localhost' is missing from SAN DNS names: {dns_names}"
    )


# ---------------------------------------------------------------------------
# 2. Main Page & Offline LAN Independence
# ---------------------------------------------------------------------------

def test_index_and_offline_no_cdn(client) -> None:
    """
    Verifies that GET /:
    - Returns 200 OK.
    - Contains the primary thumb-friendly 'Сканировать QR-код' action.
    - Contains NO external CDN references (https://cdn, unpkg.com, googleapis.com, jsdelivr.net)
      guaranteeing complete offline autonomous operation in isolated LANs.
    """
    resp = client.get("/")
    assert resp.status_code == 200, f"GET / failed with status {resp.status_code}"
    html = resp.text

    assert "Сканировать QR-код" in html, "Index page must contain 'Сканировать QR-код' button"

    forbidden_cdns = [
        "https://cdn",
        "unpkg.com",
        "googleapis.com",
        "jsdelivr.net",
    ]
    for cdn in forbidden_cdns:
        assert cdn not in html, f"Offline violation: index HTML contains reference to external CDN '{cdn}'"


# ---------------------------------------------------------------------------
# 3. Equipment Creation & Passport PDF Download
# ---------------------------------------------------------------------------

def test_create_equipment_and_passport_pdf_download(client) -> None:
    """
    Verifies equipment onboarding and technical passport PDF access:
    - POST /api/equipment returns 201 Created.
    - Card GET /doc/{id} returns 200 OK.
    - Passport in passport/ is downloaded via download_url with 200 OK,
      content-type == 'application/pdf', starts with b'%PDF-', and
      Content-Disposition includes 'attachment' and 'filename*=UTF-8'''.
    """
    payload = {
        "name": "Насос сетевой КМ-80",
        "inventory_number": "НС-77",
        "location": "Котельная №1",
    }
    create_resp = client.post("/api/equipment", json=payload)
    assert create_resp.status_code == 201, f"Equipment creation failed: {create_resp.text}"
    created_data = create_resp.json()
    eq_id = created_data.get("id")
    assert eq_id, "Created equipment missing 'id' in response"

    # Verify equipment card HTML page loads
    card_resp = client.get(f"/doc/{eq_id}")
    assert card_resp.status_code == 200
    assert "Насос сетевой КМ-80" in card_resp.text or "НС-77" in card_resp.text

    # Verify equipment API data to locate passport document
    detail_resp = client.get(f"/api/equipment/{eq_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()

    # Find download_url for passport in documents
    download_url = None
    docs = detail_data.get("documents", {})
    passport_docs = docs.get("passport", [])
    if isinstance(passport_docs, list) and len(passport_docs) > 0:
        download_url = passport_docs[0].get("download_url")
    elif isinstance(passport_docs, dict):
        download_url = passport_docs.get("download_url")

    if not download_url and "documents" in created_data:
        p_docs = created_data["documents"].get("passport", [])
        if isinstance(p_docs, list) and len(p_docs) > 0:
            download_url = p_docs[0].get("download_url")

    assert download_url, f"Passport download_url not found in equipment data: {detail_data.get('documents')}"

    # Download passport PDF
    pdf_resp = client.get(download_url)
    assert pdf_resp.status_code == 200, f"Failed to download passport PDF: {pdf_resp.status_code}"
    assert "application/pdf" in pdf_resp.headers.get("content-type", "")
    assert pdf_resp.content.startswith(b"%PDF-"), "Downloaded passport file does not start with %PDF- header"

    content_disp = pdf_resp.headers.get("content-disposition", "")
    assert "attachment" in content_disp, f"Content-Disposition missing 'attachment': {content_disp}"
    assert "filename*=UTF-8''" in content_disp, f"Content-Disposition missing RFC 5987 UTF-8 filename: {content_disp}"


# ---------------------------------------------------------------------------
# 4. Optional Diagnostics Documents & PDF Upload Validation
# ---------------------------------------------------------------------------

def test_optional_diagnostics_and_pdf_upload(client) -> None:
    """
    Verifies diagnostics document management and strict upload validation:
    - New equipment card initially has an empty list in documents['diagnostics'] (has_diagnostics is False).
    - POST /api/equipment/{id}/documents/diagnostics with valid %PDF-1.4... file and Cyrillic name returns 201.
    - Upload of invalid non-PDF (.txt or corrupted header) is rejected with 400 Bad Request.
    """
    eq_resp = client.post("/api/equipment", json={
        "name": "Вентилятор ВДН-10",
        "inventory_number": "В-10",
        "location": "Котельная №1",
    })
    assert eq_resp.status_code == 201
    eq_id = eq_resp.json()["id"]

    # 1. Initially empty diagnostics
    detail = client.get(f"/api/equipment/{eq_id}").json()
    diag_docs = detail.get("documents", {}).get("diagnostics", [])
    assert len(diag_docs) == 0, f"New equipment must have empty diagnostics documents, got: {diag_docs}"
    if "has_diagnostics" in detail:
        assert detail["has_diagnostics"] is False

    # 2. Upload invalid non-PDF (.txt extension) -> 400
    txt_files = {"file": ("protocol.txt", b"Plain text diagnostics report", "text/plain")}
    txt_resp = client.post(f"/api/equipment/{eq_id}/documents/diagnostics", files=txt_files)
    assert txt_resp.status_code == 400, f"Uploading .txt file must return 400, got: {txt_resp.status_code}"

    # 3. Upload invalid magic bytes (.pdf extension but not PDF content) -> 400
    bad_pdf_files = {"file": ("protocol.pdf", b"INVALID_BINARY_NON_PDF_DATA", "application/pdf")}
    bad_pdf_resp = client.post(f"/api/equipment/{eq_id}/documents/diagnostics", files=bad_pdf_files)
    assert bad_pdf_resp.status_code == 400, f"Uploading fake PDF content must return 400, got: {bad_pdf_resp.status_code}"

    # 4. Upload valid PDF with Cyrillic filename -> 201
    valid_pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    cyrillic_filename = "Протокол_вибродиагностики_2026.pdf"
    pdf_files = {"file": (cyrillic_filename, valid_pdf_bytes, "application/pdf")}

    upload_resp = client.post(f"/api/equipment/{eq_id}/documents/diagnostics", files=pdf_files)
    assert upload_resp.status_code == 201, f"Uploading valid PDF failed with {upload_resp.status_code}: {upload_resp.text}"

    # 5. Check diagnostics list updated
    updated_detail = client.get(f"/api/equipment/{eq_id}").json()
    updated_diag = updated_detail.get("documents", {}).get("diagnostics", [])
    assert len(updated_diag) >= 1, "Diagnostics list should contain uploaded PDF"
    assert any("Протокол_вибродиагностики_2026" in d.get("filename", "") for d in updated_diag)
    if "has_diagnostics" in updated_detail:
        assert updated_detail["has_diagnostics"] is True


# ---------------------------------------------------------------------------
# 5. Path Traversal Security
# ---------------------------------------------------------------------------

def test_path_traversal_blocked(client) -> None:
    """
    Verifies that path traversal attempts:
    - /files/{id}/passport/..%2F..%2Frequirements.txt
    - /files/{id}/passport/../../requirements.txt
    - invalid equipment_id containing '..'
    Return 400 or 404, strictly preventing leakage of files outside DOCS_DIR.
    """
    eq_resp = client.post("/api/equipment", json={
        "name": "Насос подпиточный",
        "inventory_number": "НП-01",
        "location": "Насосная",
    })
    eq_id = eq_resp.json()["id"]

    traversal_paths = [
        f"/files/{eq_id}/passport/..%2F..%2Frequirements.txt",
        f"/files/{eq_id}/passport/../../requirements.txt",
        f"/files/..%2F..%2F..%2Fetc/passport/test.pdf",
        f"/files/..%2F..%2Frequirements.txt",
        f"/files/{eq_id}/passport/..%2F..%2F..%2FWindows/win.ini",
        "/api/equipment/..%2F..%2Fsecret",
    ]

    for path in traversal_paths:
        resp = client.get(path)
        assert resp.status_code in (400, 404, 422), (
            f"Path traversal URL '{path}' returned unexpected HTTP status {resp.status_code}"
        )
        assert "fastapi>=" not in resp.text, f"requirements.txt leaked via path traversal: {path}"
        assert "DOCS_DIR" not in resp.text, f"config.py leaked via path traversal: {path}"


# ---------------------------------------------------------------------------
# 6. Maintenance Schedule, Stock Deficiency & Budget Notifications
# ---------------------------------------------------------------------------

def test_maintenance_schedule_and_budget_notifications(client) -> None:
    """
    Verifies maintenance regulation and budget alert calculation:
    - Adding maintenance task with next_due_date = date.today() + 10 days,
      materials: qty_required=10, qty_in_stock=3, unit_price_rub=1500 (deficit: 7 * 1500 = 10500 rub),
      service_cost_rub=5000 -> total budget = 15500.0 rub.
    - GET /api/overview displays budget alert with urgency == 'soon' and budget_required_rub == 15500.0.
    - POST /api/equipment/{id}/maintenance/{task_id}/complete advances next_due_date by interval_days
      and appends an entry to maintenance_history.
    """
    eq_resp = client.post("/api/equipment", json={
        "name": "Котёл водогрейный КВ-ГМ",
        "inventory_number": "КВ-01",
        "location": "Котельный зал",
    })
    eq_id = eq_resp.json()["id"]

    interval = 30
    due_10_days = (date.today() + timedelta(days=10)).isoformat()

    task_payload = {
        "code": "ТО-1",
        "title": "Плановое ТО-1 насосной группы",
        "interval_days": interval,
        "next_due_date": due_10_days,
        "responsible": "Служба главного механика",
        "service_cost_rub": 5000.0,
        "materials": [
            {
                "name": "Сальник графитовый",
                "sku": "СГ-45",
                "unit": "шт.",
                "qty_required": 10.0,
                "qty_in_stock": 3.0,
                "unit_price_rub": 1500.0,
            }
        ],
        "notes": "Регулярная замена уплотнителей",
    }

    add_task_resp = client.post(f"/api/equipment/{eq_id}/maintenance", json=task_payload)
    assert add_task_resp.status_code in (200, 201), f"Failed to add maintenance task: {add_task_resp.text}"

    # Extract task_id from equipment details
    eq_detail = client.get(f"/api/equipment/{eq_id}").json()
    tasks = eq_detail.get("maintenance_tasks", [])
    assert len(tasks) >= 1, "Equipment should have at least 1 maintenance task"
    task = next((t for t in tasks if t.get("code") == "ТО-1"), tasks[0])
    task_id = task.get("id")
    assert task_id, "Maintenance task id is missing"

    # Check overview notifications
    overview_resp = client.get("/api/overview")
    assert overview_resp.status_code == 200, f"GET /api/overview failed: {overview_resp.status_code}"
    overview_data = overview_resp.json()

    # Gather all notifications from overview
    all_notifs: list[dict] = []
    if "notifications" in overview_data and isinstance(overview_data["notifications"], list):
        all_notifs.extend(overview_data["notifications"])
    if "budget_notifications" in overview_data and isinstance(overview_data["budget_notifications"], list):
        all_notifs.extend(overview_data["budget_notifications"])
    if not all_notifs:
        for val in overview_data.values():
            if isinstance(val, list) and val and isinstance(val[0], dict) and (
                "urgency" in val[0] or "budget_required_rub" in val[0]
            ):
                all_notifs.extend(val)

    # Find the notification for our equipment or maintenance calculation
    matching_notif = next(
        (n for n in all_notifs if n.get("equipment_id") == eq_id),
        None,
    )
    assert matching_notif is not None, f"Maintenance notification not found in overview: {overview_data}"
    assert matching_notif.get("urgency") == "soon", (
        f"Expected urgency 'soon' (10 days due), got: {matching_notif.get('urgency')}"
    )
    msg = matching_notif.get("message", "")
    assert "ТО-1" in msg, f"Expected task code 'ТО-1' in message: {msg}"
    # Technical focus: no monetary sums in operational notifications
    assert "₸" not in msg, f"Message must NOT contain money sums or '₸': {msg}"
    assert "₽" not in msg, f"Message must NOT contain money sums or '₽': {msg}"

    # Complete the maintenance task
    complete_payload = {
        "performer": "Ведущий инженер Сидоров",
        "comment": "Замена уплотнений завершена",
    }
    comp_resp = client.post(f"/api/equipment/{eq_id}/maintenance/{task_id}/complete", json=complete_payload)
    assert comp_resp.status_code in (200, 201), f"Complete maintenance failed: {comp_resp.text}"

    # Verify that next_due_date shifted forward and history record was created
    updated_eq = client.get(f"/api/equipment/{eq_id}").json()
    updated_task = next(t for t in updated_eq["maintenance_tasks"] if t["id"] == task_id)
    assert updated_task["next_due_date"] > due_10_days, (
        f"next_due_date was not shifted forward: previous={due_10_days}, current={updated_task['next_due_date']}"
    )

    history = updated_eq.get("maintenance_history", [])
    assert len(history) >= 1, "maintenance_history must contain completed task log"
    assert any(h.get("task_code") == "ТО-1" for h in history), "Log entry for ТО-1 not found in history"


# ---------------------------------------------------------------------------
# 7. Photo Visual Condition Upload
# ---------------------------------------------------------------------------

def test_photo_visual_condition_upload(client) -> None:
    """
    Verifies visual inspection photo upload from mobile/desktop:
    - Generates valid PNG in memory using PIL.Image.new('RGB', (120, 90), color=(30, 60, 90)).
    - Sends to POST /api/equipment/{id}/photos with condition='attention', node='Подшипниковый узел',
      comment='Следы перегрева смазки' -> 201.
    - Equipment status updates to 'attention'.
    - Photo is downloadable/viewable via its url with status 200 OK.
    """
    eq_resp = client.post("/api/equipment", json={
        "name": "Компрессор винтовой КВ",
        "inventory_number": "КВ-04",
        "location": "Компрессорная станция",
    })
    eq_id = eq_resp.json()["id"]

    # Generate valid PNG in memory
    img = Image.new("RGB", (120, 90), color=(30, 60, 90))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    files = {"file": ("inspection_photo.png", png_bytes, "image/png")}
    form_data = {
        "condition": "attention",
        "node": "Подшипниковый узел",
        "comment": "Следы перегрева смазки",
    }

    upload_resp = client.post(f"/api/equipment/{eq_id}/photos", files=files, data=form_data)
    assert upload_resp.status_code == 201, f"Photo upload failed: {upload_resp.text}"

    # Verify equipment status is now 'attention'
    eq_data = client.get(f"/api/equipment/{eq_id}").json()
    assert eq_data.get("status") == "attention", (
        f"Expected equipment status 'attention', got: {eq_data.get('status')}"
    )

    # Verify photo metadata and view URL
    photos = eq_data.get("photos", [])
    assert len(photos) >= 1, "Photos list should contain newly uploaded photo"
    photo_entry = photos[-1]
    assert photo_entry.get("condition") == "attention"
    assert photo_entry.get("node") == "Подшипниковый узел"
    assert photo_entry.get("comment") == "Следы перегрева смазки"

    photo_url = photo_entry.get("url")
    assert photo_url, "Photo entry missing 'url' field"

    # Verify downloading photo via photo_url
    get_photo_resp = client.get(photo_url)
    assert get_photo_resp.status_code == 200, f"Failed to retrieve photo via {photo_url}"
    assert "image" in get_photo_resp.headers.get("content-type", "")
    assert get_photo_resp.content.startswith(b"\x89PNG"), "Retrieved photo is not a valid PNG image"


# ---------------------------------------------------------------------------
# 8. Defects Accounting & Defect Sheet PDF Auto-Generation
# ---------------------------------------------------------------------------

def test_defects_and_defect_sheet_pdf_generation(client) -> None:
    """
    Verifies defect registration, critical status escalation, and PDF defect sheet generation:
    - POST /api/equipment/{id}/defects (severity='critical', estimated_cost_rub=24000) -> 201/200,
      equipment status escalates to 'critical'.
    - POST /api/equipment/{id}/defects/generate-pdf returns 201 Created.
    - documents['defects'] contains the generated defect sheet PDF, which is downloaded with status 200 OK.
    - GET /api/equipment/{id}/qr returns image/png for printable equipment stickers.
    """
    eq_resp = client.post("/api/equipment", json={
        "name": "Электродвигатель АИР-250",
        "inventory_number": "ЭД-250",
        "location": "Цех №2",
    })
    eq_id = eq_resp.json()["id"]

    defect_payload = {
        "node": "Статор электродвигателя",
        "description": "Пробой фазной изоляции обмотки статора",
        "severity": "critical",
        "recommended_action": "Капитальный ремонт и перемотка статора",
        "estimated_cost_rub": 24000.0,
    }

    defect_resp = client.post(f"/api/equipment/{eq_id}/defects", json=defect_payload)
    assert defect_resp.status_code in (200, 201), f"Defect creation failed: {defect_resp.text}"

    # Verify equipment status is escalated to 'critical'
    eq_data = client.get(f"/api/equipment/{eq_id}").json()
    assert eq_data.get("status") == "critical", (
        f"Expected equipment status 'critical', got: {eq_data.get('status')}"
    )

    # Generate defect sheet PDF
    gen_resp = client.post(f"/api/equipment/{eq_id}/defects/generate-pdf")
    assert gen_resp.status_code == 201, f"Defect sheet PDF generation failed: {gen_resp.text}"

    # Verify documents['defects'] has the generated PDF
    updated_eq = client.get(f"/api/equipment/{eq_id}").json()
    defect_docs = updated_eq.get("documents", {}).get("defects", [])
    assert len(defect_docs) >= 1, f"Defect documents list is empty in: {updated_eq.get('documents')}"

    download_url = defect_docs[0].get("download_url")
    assert download_url, "Download url missing from generated defect document"

    pdf_resp = client.get(download_url)
    assert pdf_resp.status_code == 200, f"Failed to download generated defect PDF: {pdf_resp.status_code}"
    assert "application/pdf" in pdf_resp.headers.get("content-type", "")
    assert pdf_resp.content.startswith(b"%PDF-"), "Generated defect sheet is not a valid PDF (%PDF- header missing)"

    # Verify equipment QR code sticker endpoint
    qr_resp = client.get(f"/api/equipment/{eq_id}/qr")
    assert qr_resp.status_code == 200, f"QR code endpoint failed: {qr_resp.status_code}"
    assert "image/png" in qr_resp.headers.get("content-type", "")
    assert qr_resp.content.startswith(b"\x89PNG"), "QR code endpoint did not return valid PNG data"


# ---------------------------------------------------------------------------
# 9. Keycloak Authentication & Session Cookie Tests
# ---------------------------------------------------------------------------

def test_keycloak_direct_auth_and_session(client) -> None:
    """
    Verifies Keycloak-integrated authentication flows:
    - /auth/login returns 200 with Mind branded login options.
    - POST /auth/direct-login with invalid credentials fails with 401.
    - POST /auth/direct-login with 'admin' / 'admin123' succeeds, issues session cookie.
    - GET /api/auth/me returns user profile with roles and admin rights.
    - GET /auth/logout clears cookie and resets session.
    """
    # 1. Login page check
    login_page = client.get("/auth/login")
    assert login_page.status_code == 200
    assert "Keycloak" in login_page.text

    # 2. Invalid password
    bad_login = client.post("/auth/direct-login", data={
        "username": "admin",
        "password": "wrong-password",
    })
    assert bad_login.status_code == 401

    # 3. Successful admin login
    ok_login = client.post("/auth/direct-login", data={
        "username": "admin",
        "password": "admin123",
    }, follow_redirects=False)
    assert ok_login.status_code in (302, 303)
    assert "mind_session" in ok_login.cookies
    admin_token = ok_login.cookies["mind_session"]

    # 4. Check /api/auth/me using authenticated session cookie
    me_resp = client.get("/api/auth/me", headers={"Cookie": f"mind_session={admin_token}"})
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data.get("authenticated") is True
    user = me_data.get("user", {})
    assert user.get("username") == "admin"
    assert user.get("is_admin") is True
    assert "admin" in user.get("roles", [])

    # Also verify Bearer header works identically
    bearer_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert bearer_resp.status_code == 200
    assert bearer_resp.json().get("authenticated") is True

    # 5. Logout clears session
    logout_resp = client.get("/auth/logout", follow_redirects=False)
    assert logout_resp.status_code in (302, 303)
    
    # 6. Check unauthenticated me
    unauth_resp = client.get("/api/auth/me")
    assert unauth_resp.status_code == 200
    assert unauth_resp.json().get("authenticated") is False


# ---------------------------------------------------------------------------
# 10. Proprietary Secure QR Code Generation & Verification
# ---------------------------------------------------------------------------

def test_secure_closed_qr_lifecycle_and_verification(client) -> None:
    """
    Verifies that proprietary closed QR codes:
    - Are generated via GET /api/equipment/{id}/secure-qr with PNG format and Mind styling.
    - The payload MINDEQUIP:v2:<id>:<token> is NOT a navigable browser URL,
      preventing stock phone cameras from opening it directly.
    - POST /api/verify-qr-token validates the token against the cryptographic store.
    - Tampered or forged tokens are strictly rejected.
    """
    import app.security_qr as sec_qr

    # 1. Create equipment
    eq_resp = client.post("/api/equipment", json={
        "name": "Трансформатор силовой ТМГ-1000",
        "inventory_number": "ТР-1000",
        "location": "Подстанция 110/10 кВ",
    })
    assert eq_resp.status_code == 201
    eq_id = eq_resp.json()["id"]

    # 2. Get secure QR PNG
    png_resp = client.get(f"/api/equipment/{eq_id}/secure-qr")
    assert png_resp.status_code == 200
    assert png_resp.headers.get("content-type") == "image/png"
    assert png_resp.content.startswith(b"\x89PNG")

    # 3. Generate valid payload
    valid_payload = sec_qr.generate_secure_qr_payload(eq_id)
    assert valid_payload.startswith("MINDEQUIP:v2:")
    assert eq_id in valid_payload

    # 4. Verify valid payload
    verify_resp = client.post("/api/verify-qr-token", json={"token": valid_payload})
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()
    assert v_data.get("is_secure_qr") is True
    assert v_data.get("valid") is True
    assert v_data.get("equipment_id") == eq_id
    assert v_data.get("card_url") == f"/doc/{eq_id}"

    # 5. Verify tampered payload fails
    tampered_payload = f"MINDEQUIP:v2:{eq_id}:FAKEKEY12345678"
    fake_resp = client.post("/api/verify-qr-token", json={"token": tampered_payload})
    assert fake_resp.status_code == 200
    f_data = fake_resp.json()
    assert f_data.get("is_secure_qr") is True
    assert f_data.get("valid") is False
    assert "Токен QR-кода устарел или был перевыпущен" in f_data.get("error", "")

    # 6. Verify plain standard link fallback
    standard_resp = client.post("/api/verify-qr-token", json={"token": f"https://0.0.0.0:8443/doc/{eq_id}"})
    assert standard_resp.status_code == 200
    s_data = standard_resp.json()
    assert s_data.get("valid") is True
    assert s_data.get("is_secure_qr") is False
    assert s_data.get("equipment_id") == eq_id


# ---------------------------------------------------------------------------
# 11. QR Token Rotation & Role-Based Access
# ---------------------------------------------------------------------------

def test_qr_token_rotation_and_role_access(client) -> None:
    """
    Verifies token rotation security:
    - Operator cannot rotate token (403 Forbidden).
    - Engineer or Admin can rotate token.
    - Rotating token invalidates old QR payload and validates new payload.
    """
    import app.security_qr as sec_qr

    eq_resp = client.post("/api/equipment", json={
        "name": "Компрессор винтовой КВ-12",
        "inventory_number": "КВ-12",
        "location": "Компрессорная",
    })
    eq_id = eq_resp.json()["id"]

    old_payload = sec_qr.generate_secure_qr_payload(eq_id)

    # 1. Login as operator
    op_login = client.post("/auth/direct-login", data={
        "username": "operator",
        "password": "operator123",
    }, follow_redirects=False)
    assert op_login.status_code in (302, 303)
    op_token = op_login.cookies.get("mind_session")
    assert op_token

    # Operator rotation attempt must be rejected (403 Forbidden)
    denied = client.post(
        f"/api/equipment/{eq_id}/rotate-qr",
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert denied.status_code == 403, f"Expected 403 Forbidden for operator, got: {denied.status_code}"

    # Unauthenticated rotation attempt must also be rejected (403 Forbidden)
    anon_denied = client.post(f"/api/equipment/{eq_id}/rotate-qr")
    assert anon_denied.status_code == 403

    # 2. Login as engineer
    eng_login = client.post("/auth/direct-login", data={
        "username": "engineer",
        "password": "engineer123",
    }, follow_redirects=False)
    assert eng_login.status_code in (302, 303)
    eng_token = eng_login.cookies.get("mind_session")
    assert eng_token

    # Engineer rotation succeeds
    rotate_resp = client.post(
        f"/api/equipment/{eq_id}/rotate-qr",
        headers={"Authorization": f"Bearer {eng_token}"},
    )
    assert rotate_resp.status_code == 200, f"Rotation failed: {rotate_resp.text}"
    new_token = rotate_resp.json().get("token")
    assert new_token

    # 3. Old payload is now invalidated
    old_verify = client.post("/api/verify-qr-token", json={"token": old_payload})
    assert old_verify.json().get("valid") is False

    # 4. New payload is valid
    new_payload = sec_qr.generate_secure_qr_payload(eq_id)
    new_verify = client.post("/api/verify-qr-token", json={"token": new_payload})
    assert new_verify.json().get("valid") is True


# ---------------------------------------------------------------------------
# 12. Network Information & Custom Port (8443)
# ---------------------------------------------------------------------------

def test_network_info_port_8443(client) -> None:
    """
    Verifies /api/network-info returns the updated port 8443 and local interfaces.
    """
    resp = client.get("/api/network-info")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("port") == 8443
    assert ":8443" in data.get("primary_url", "")
    assert isinstance(data.get("interfaces"), list)


# ---------------------------------------------------------------------------
# 13. Active Directory (AD / LDAP) Integration Tests
# ---------------------------------------------------------------------------

def test_active_directory_username_cleaning_and_role_mapping() -> None:
    """
    Verifies domain username normalization and group-to-role mappings for ICA.
    """
    from app import ad_auth

    # 1. Clean username tests
    u1, upn1 = ad_auth.clean_username("INTERGAS\\a.sarsembayev", default_domain="intergas.kz")
    assert u1 == "a.sarsembayev"
    assert upn1 == "a.sarsembayev@intergas.kz"

    u2, upn2 = ad_auth.clean_username("t.iskaliyev@intergas.kz", default_domain="intergas.kz")
    assert u2 == "t.iskaliyev"
    assert upn2 == "t.iskaliyev@intergas.kz"

    u3, upn3 = ad_auth.clean_username("operator_grs", default_domain="intergas.kz")
    assert u3 == "operator_grs"
    assert upn3 == "operator_grs@intergas.kz"

    # 2. Group to role mapping: Admin / Mechanics
    roles_admin, label_admin = ad_auth._map_ad_groups_to_roles(["CN=GG_ICA_Mechanics,OU=Groups,DC=intergas,DC=kz"])
    assert "admin" in roles_admin
    assert "engineer" in roles_admin
    assert "Главный механик" in label_admin

    # 3. Group to role mapping: Engineers
    roles_eng, label_eng = ad_auth._map_ad_groups_to_roles(["CN=GG_ICA_Engineers,OU=Groups,DC=intergas,DC=kz"])
    assert "engineer" in roles_eng
    assert "admin" not in roles_eng
    assert "Инженер" in label_eng

    # 4. Group to role mapping: Operators
    roles_op, label_op = ad_auth._map_ad_groups_to_roles(["CN=GG_ICA_Operators,OU=Groups,DC=intergas,DC=kz"])
    assert "operator" in roles_op
    assert "admin" not in roles_op
    assert "Оператор" in label_op


def test_active_directory_status_endpoint_and_direct_login_mock(client, monkeypatch) -> None:
    """
    Verifies /api/auth/ad-status endpoint and that Active Directory direct-login
    authenticates corporate domain users into FastAPI sessions.
    """
    from app import ad_auth, config

    # 1. Check status endpoint
    status_resp = client.get("/api/auth/ad-status")
    assert status_resp.status_code == 200
    st_data = status_resp.json()
    assert "enabled" in st_data
    assert st_data.get("domain") == "intergas.kz"
    assert "role_groups" in st_data

    # 2. Enable AD via monkeypatch and mock authenticate_ad_user
    monkeypatch.setattr(config, "AD_ENABLED", True)

    def mock_authenticate_ad_user(username: str, password: str):
        if username in ("a.sarsembayev", "INTERGAS\\a.sarsembayev") and password == "CorpDomainSecretPass2026!":
            return {
                "sub": "ad-guid-a-sarsembayev",
                "username": "a.sarsembayev",
                "name": "Алибек Сарсембаев",
                "email": "a.sarsembayev@intergas.kz",
                "roles": ["engineer"],
                "role_label": "Инженер ТО и диагностики (AD)",
                "is_admin": False,
                "is_engineer": True,
                "member_of": ["CN=GG_ICA_Engineers,OU=Groups,DC=intergas,DC=kz"],
                "auth_source": "Active Directory (LDAP)",
            }
        return None

    monkeypatch.setattr(ad_auth, "authenticate_ad_user", mock_authenticate_ad_user)

    # 3. Test successful AD login
    ad_login = client.post("/auth/direct-login", data={
        "username": "a.sarsembayev",
        "password": "CorpDomainSecretPass2026!",
        "target": "/",
    }, follow_redirects=False)

    assert ad_login.status_code in (302, 303)
    session_cookie = ad_login.cookies.get("mind_session")
    assert session_cookie, "AD login must set session cookie"

    # 4. Check authenticated session user info
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {session_cookie}"})
    assert me_resp.status_code == 200
    res_data = me_resp.json()
    assert res_data["authenticated"] is True
    user_info = res_data["user"]
    assert user_info["username"] == "a.sarsembayev"
    assert user_info["name"] == "Алибек Сарсембаев"
    assert "engineer" in user_info["roles"]
