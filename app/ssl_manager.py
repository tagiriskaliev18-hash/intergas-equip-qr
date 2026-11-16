from __future__ import annotations

import datetime
import ipaddress
import logging
import socket
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID, NameOID

from app import config

logger = logging.getLogger(__name__)


def get_local_ipv4_addresses() -> list[str]:
    """
    Определяет активные локальные IPv4-адреса хоста.
    Использует комбинацию UDP-сокета к широковещательному/маршрутизируемому адресу
    и socket.getaddrinfo, исключая 127.0.0.1 и 0.0.0.0.
    """
    ips: set[str] = set()

    # Способ 1: UDP-сокет без отправки пакетов
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            sock_ip = s.getsockname()[0]
            if sock_ip and sock_ip not in ("127.0.0.1", "0.0.0.0"):
                ips.add(sock_ip)
    except Exception:
        pass

    # Способ 2: socket.getaddrinfo по имени хоста
    try:
        hostname = socket.gethostname()
        addr_infos = socket.getaddrinfo(hostname, None, socket.AF_INET)
        for item in addr_infos:
            ip = item[4][0]
            if ip and ip not in ("127.0.0.1", "0.0.0.0"):
                ips.add(ip)
    except Exception:
        pass

    # Сортировка по числовым октетам IP-адреса
    def _ip_sort_key(ip_str: str) -> tuple[int, ...]:
        try:
            return tuple(int(part) for part in ip_str.split("."))
        except Exception:
            return (0, 0, 0, 0)

    return sorted(ips, key=_ip_sort_key)


def ensure_self_signed_cert(
    cert_path: Path | None = None,
    key_path: Path | None = None,
    force_regen: bool = False,
    validity_days: int = 365,
) -> dict[str, Any]:
    """
    Проверяет наличие и валидность TLS-сертификата.
    Если сертификат отсутствует, истёк или в нём не хватает актуальных LAN IP-адресов,
    генерирует новую ключевую пару RSA-2048 и самоподписанный X.509v3 сертификат.

    Apple iOS / Safari требует validity_days <= 825 (рекомендуется 365).
    """
    target_cert = (cert_path or config.CERT_FILE).resolve()
    target_key = (key_path or config.KEY_FILE).resolve()
    validity_days = min(max(validity_days, 1), 825)

    lan_ips = get_local_ipv4_addresses()
    required_ips = {"0.0.0.0", "127.0.0.1"}.union(lan_ips)

    regenerate_needed = force_regen or not target_cert.exists() or not target_key.exists()

    existing_san_ips: set[str] = set()

    if not regenerate_needed:
        try:
            cert_bytes = target_cert.read_bytes()
            cert = x509.load_pem_x509_certificate(cert_bytes)

            # Проверка срока действия
            if hasattr(cert, "not_valid_after_utc"):
                expiry_dt = cert.not_valid_after_utc
                now_dt = datetime.datetime.now(datetime.timezone.utc)
            else:
                expiry_dt = cert.not_valid_after  # type: ignore[attr-defined]
                now_dt = datetime.datetime.utcnow()

            # Если сертификат истёк или истекает менее чем через 24 часа
            if expiry_dt <= now_dt + datetime.timedelta(hours=24):
                regenerate_needed = True
            else:
                # Проверка наличия всех требуемых IP в SubjectAlternativeName
                try:
                    san_ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
                    san_ip_objs = san_ext.value.get_values_for_type(x509.IPAddress)  # type: ignore[attr-defined]
                    existing_san_ips = {str(item) for item in san_ip_objs}
                    if not required_ips.issubset(existing_san_ips):
                        regenerate_needed = True
                except Exception:
                    regenerate_needed = True
        except Exception as e:
            logger.warning("Не удалось прочитать существующий TLS-сертификат, требуется перегенерация: %s", e)
            regenerate_needed = True

    if regenerate_needed:
        logger.info("Генерация нового самоподписанного TLS-сертификата X.509v3...")
        target_cert.parent.mkdir(parents=True, exist_ok=True)
        target_key.parent.mkdir(parents=True, exist_ok=True)

        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Mind Equip"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Industrial Inspection"),
            x509.NameAttribute(NameOID.COMMON_NAME, "Mind Equip Local Server"),
        ])

        san_entries: list[x509.GeneralName] = [
            x509.IPAddress(ipaddress.IPv4Address("0.0.0.0")),
            x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
        ]
        san_ip_strings: set[str] = {"0.0.0.0", "127.0.0.1"}

        for lan_ip in lan_ips:
            try:
                ip_obj = ipaddress.IPv4Address(lan_ip)
                san_entries.append(x509.IPAddress(ip_obj))
                san_ip_strings.add(lan_ip)
            except Exception:
                pass

        san_entries.append(x509.DNSName("localhost"))
        try:
            raw_host = socket.gethostname()
            ascii_host = raw_host.encode("ascii", errors="ignore").decode("ascii").strip()
            if ascii_host and ascii_host.lower() != "localhost":
                san_entries.append(x509.DNSName(ascii_host))
        except Exception:
            pass

        now_utc = datetime.datetime.now(datetime.timezone.utc)
        cert_builder = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now_utc - datetime.timedelta(minutes=5))
            .not_valid_after(now_utc + datetime.timedelta(days=validity_days))
            .add_extension(
                x509.SubjectAlternativeName(san_entries),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True,
                    key_encipherment=True,
                    content_commitment=False,
                    data_encipherment=False,
                    key_agreement=False,
                    key_cert_sign=False,
                    crl_sign=False,
                    encipher_only=False,
                    decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
                critical=False,
            )
        )

        cert = cert_builder.sign(private_key, hashes.SHA256())

        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)

        target_key.write_bytes(key_pem)
        target_cert.write_bytes(cert_pem)
        existing_san_ips = san_ip_strings
        regenerated = True
    else:
        regenerated = False

    def _ip_sort_key(ip_str: str) -> tuple[int, ...]:
        try:
            return tuple(int(part) for part in ip_str.split("."))
        except Exception:
            return (0, 0, 0, 0)

    sorted_san_ips = sorted(existing_san_ips, key=_ip_sort_key)
    lan_urls = [f"https://{ip}:{config.PORT}" for ip in lan_ips]

    return {
        "cert_file": str(target_cert),
        "key_file": str(target_key),
        "san_ips": sorted_san_ips,
        "lan_ips": lan_ips,
        "lan_urls": lan_urls,
        "regenerated": regenerated,
    }
