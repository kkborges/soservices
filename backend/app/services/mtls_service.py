from __future__ import annotations

import hashlib
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from app.core.config import settings


@dataclass
class IssuedMaterial:
    ca_pem: str
    cert_pem: str
    key_pem: str
    subject: str
    serial: str


@dataclass
class GatewayIssuedBundle(IssuedMaterial):
    server_cert_pem: str
    server_key_pem: str


def _storage_dir() -> Path:
    path = Path(settings.MTLS_STORAGE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ca_key_path() -> Path:
    return _storage_dir() / "ca.key.pem"


def _ca_cert_path() -> Path:
    return _storage_dir() / "ca.pem"


def _entity_dir(kind: str) -> Path:
    path = _storage_dir() / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pem_bytes_private_key(key: rsa.RSAPrivateKey) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _pem_bytes_cert(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def _load_private_key(path: Path) -> rsa.RSAPrivateKey:
    return serialization.load_pem_private_key(path.read_bytes(), password=None)


def _load_cert(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


def ensure_ca() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    cert_path = _ca_cert_path()
    key_path = _ca_key_path()
    if cert_path.exists() and key_path.exists():
        return _load_cert(cert_path), _load_private_key(key_path)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SOServices"),
            x509.NameAttribute(NameOID.COMMON_NAME, settings.MTLS_CA_COMMON_NAME),
        ]
    )
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(private_key.public_key()), critical=False)
        .sign(private_key, hashes.SHA256())
    )
    key_path.write_bytes(_pem_bytes_private_key(private_key))
    cert_path.write_bytes(_pem_bytes_cert(cert))
    return cert, private_key


def _entity_paths(kind: str, entity_id: str) -> tuple[Path, Path]:
    key = hashlib.sha256(entity_id.encode("utf-8")).hexdigest()
    directory = _entity_dir(kind)
    return directory / f"{key}.cert.pem", directory / f"{key}.key.pem"


def _server_paths(entity_id: str) -> tuple[Path, Path]:
    key = hashlib.sha256(f"server:{entity_id}".encode("utf-8")).hexdigest()
    directory = _entity_dir("gateway-server")
    return directory / f"{key}.cert.pem", directory / f"{key}.key.pem"


def _normalize_dns_names(names: Iterable[str | None]) -> list[str]:
    items: list[str] = []
    for value in names:
        if not value:
            continue
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = (parsed.hostname or value).strip()
        if host and host not in items:
            items.append(host)
    return items


def _subject(kind: str, entity_id: str, tenant_id: str) -> x509.Name:
    common_name = f"las-{kind}-{entity_id[:12]}"
    return x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SOServices"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, tenant_id[:32]),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )


def _issue_certificate(
    *,
    cert_path: Path,
    key_path: Path,
    subject: x509.Name,
    issuer_cert: x509.Certificate,
    issuer_key: rsa.RSAPrivateKey,
    client_auth: bool,
    server_auth: bool,
    dns_names: Iterable[str] = (),
    ip_addrs: Iterable[str] = (),
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    if cert_path.exists() and key_path.exists():
        return _load_cert(cert_path), _load_private_key(key_path)

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer_cert.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=825))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    )

    usages = []
    if client_auth:
        usages.append(ExtendedKeyUsageOID.CLIENT_AUTH)
    if server_auth:
        usages.append(ExtendedKeyUsageOID.SERVER_AUTH)
    if usages:
        builder = builder.add_extension(x509.ExtendedKeyUsage(usages), critical=False)
    builder = builder.add_extension(x509.SubjectKeyIdentifier.from_public_key(private_key.public_key()), critical=False)
    builder = builder.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),
        critical=False,
    )

    san_entries: list[x509.GeneralName] = []
    for name in _normalize_dns_names(dns_names):
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            san_entries.append(x509.DNSName(name))
    for address in ip_addrs:
        try:
            san_entries.append(x509.IPAddress(ipaddress.ip_address(address)))
        except ValueError:
            continue
    if san_entries:
        builder = builder.add_extension(x509.SubjectAlternativeName(san_entries), critical=False)

    cert = builder.sign(issuer_key, hashes.SHA256())
    key_path.write_bytes(_pem_bytes_private_key(private_key))
    cert_path.write_bytes(_pem_bytes_cert(cert))
    return cert, private_key


def issue_agent_material(*, tenant_id: str, token_id: str, hostname: str | None = None) -> IssuedMaterial:
    ca_cert, ca_key = ensure_ca()
    cert_path, key_path = _entity_paths("agent-client", token_id)
    cert, key = _issue_certificate(
        cert_path=cert_path,
        key_path=key_path,
        subject=_subject("agent", token_id, tenant_id),
        issuer_cert=ca_cert,
        issuer_key=ca_key,
        client_auth=True,
        server_auth=False,
        dns_names=[hostname] if hostname else [],
    )
    return IssuedMaterial(
        ca_pem=_pem_bytes_cert(ca_cert).decode("utf-8"),
        cert_pem=_pem_bytes_cert(cert).decode("utf-8"),
        key_pem=_pem_bytes_private_key(key).decode("utf-8"),
        subject=cert.subject.rfc4514_string(),
        serial=hex(cert.serial_number),
    )


def issue_gateway_material(
    *,
    tenant_id: str,
    gateway_id: str,
    hostname: str | None = None,
    public_endpoint: str | None = None,
) -> GatewayIssuedBundle:
    ca_cert, ca_key = ensure_ca()

    client_cert_path, client_key_path = _entity_paths("gateway-client", gateway_id)
    client_cert, client_key = _issue_certificate(
        cert_path=client_cert_path,
        key_path=client_key_path,
        subject=_subject("gateway", gateway_id, tenant_id),
        issuer_cert=ca_cert,
        issuer_key=ca_key,
        client_auth=True,
        server_auth=False,
        dns_names=[hostname] if hostname else [],
    )

    server_cert_path, server_key_path = _server_paths(gateway_id)
    server_cert, server_key = _issue_certificate(
        cert_path=server_cert_path,
        key_path=server_key_path,
        subject=_subject("gateway-server", gateway_id, tenant_id),
        issuer_cert=ca_cert,
        issuer_key=ca_key,
        client_auth=False,
        server_auth=True,
        dns_names=[hostname, public_endpoint, "localhost", "127.0.0.1"],
        ip_addrs=["127.0.0.1"],
    )

    return GatewayIssuedBundle(
        ca_pem=_pem_bytes_cert(ca_cert).decode("utf-8"),
        cert_pem=_pem_bytes_cert(client_cert).decode("utf-8"),
        key_pem=_pem_bytes_private_key(client_key).decode("utf-8"),
        subject=client_cert.subject.rfc4514_string(),
        serial=hex(client_cert.serial_number),
        server_cert_pem=_pem_bytes_cert(server_cert).decode("utf-8"),
        server_key_pem=_pem_bytes_private_key(server_key).decode("utf-8"),
    )


def issue_api_server_certificate() -> tuple[Path, Path, Path]:
    ca_cert, ca_key = ensure_ca()
    cert_path = _storage_dir() / "api-server.cert.pem"
    key_path = _storage_dir() / "api-server.key.pem"
    _issue_certificate(
        cert_path=cert_path,
        key_path=key_path,
        subject=x509.Name(
            [
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SOServices"),
                x509.NameAttribute(NameOID.COMMON_NAME, "api.soservices.com.br"),
            ]
        ),
        issuer_cert=ca_cert,
        issuer_key=ca_key,
        client_auth=False,
        server_auth=True,
        dns_names=["api.soservices.com.br", "mtls-api.soservices.com.br", "localhost", "192.168.0.108"],
        ip_addrs=["127.0.0.1", "192.168.0.108"],
    )
    return _ca_cert_path(), cert_path, key_path
