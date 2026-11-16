from __future__ import annotations

import io
import qrcode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_png(target_url: str) -> bytes:
    """
    Генерирует чёткий QR-код в формате PNG для сканирования камерой смартфона.
    Использует уровень коррекции ошибок M (15%) и компактные поля (border=2).
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(target_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#09090F", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
