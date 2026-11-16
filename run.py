from __future__ import annotations

import argparse
import sys
from pathlib import Path

import uvicorn

from app import config
from app.ssl_manager import ensure_self_signed_cert


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mind-equip",
        description="Mind Equip — Локальный автономный узел технической документации и ТО оборудования",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=config.HOST,
        help=f"Адрес привязки веб-сервера (по умолчанию: {config.HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.PORT,
        help=f"TCP-порт сервиса (по умолчанию: {config.PORT})",
    )
    parser.add_argument(
        "--regen-cert",
        action="store_true",
        default=False,
        help="Принудительно перегенерировать самоподписанный TLS-сертификат",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # 1. Проверка и подготовка самоподписанного TLS-сертификата
    ssl_info = ensure_self_signed_cert(force_regen=args.regen_cert)

    # 2. Вывод приборной сводки запуска в консоль
    print("=" * 70)
    print("  MIND EQUIP // УЗЕЛ ПАСПОРТИЗАЦИИ И ТО ОБОРУДОВАНИЯ (TLS 5810)")
    print("=" * 70)
    print(f"  • Адрес привязки:      https://{args.host}:{args.port}")
    print(f"  • TLS-сертификат:      {ssl_info['cert_file']}")
    print(f"  • Приватный ключ:      {ssl_info['key_file']}")
    print(f"  • SAN IP-адреса:       {', '.join(ssl_info['san_ips'])}")
    print(f"  • Статус сертификата:  {'ПЕРЕГЕНЕРИРОВАН' if ssl_info['regenerated'] else 'ДЕЙСТВИТЕЛЕН (OK)'}")
    print("-" * 70)
    print("  ПОДКЛЮЧЕНИЕ СО СМАРТФОНА ПО WI-FI (сканирование QR-кодов):")
    if ssl_info["lan_urls"]:
        for url in ssl_info["lan_urls"]:
            print(f"    ➔  {url}")
    else:
        print(f"    ➔  https://localhost:{args.port}")
    print("=" * 70)
    print("  Для остановки сервера нажмите Ctrl + C\n")

    # 3. Запуск HTTP/TLS сервера
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        ssl_keyfile=ssl_info["key_file"],
        ssl_certfile=ssl_info["cert_file"],
        log_level="info",
    )


if __name__ == "__main__":
    main()
