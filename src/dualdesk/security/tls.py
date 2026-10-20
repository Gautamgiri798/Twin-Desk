from __future__ import annotations

import datetime
import hashlib
import hmac
import ipaddress
import logging
import ssl
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


def compute_cert_fingerprint(cert_der: bytes) -> str:
    """Computes standard DualDesk SHA-256 fingerprint from raw DER certificate bytes."""
    digest = hashlib.sha256(cert_der).hexdigest()
    return f"SHA256:{digest[:8]}-{digest[8:16]}-{digest[16:24]}-{digest[24:32]}".upper()


def generate_self_signed_cert(
    cert_path: Path,
    key_path: Path,
    device_id: str,
    common_name: str = "dualdesk.local",
) -> str:
    """
    Generates an RSA 2048 private key and self-signed X.509 certificate for TLS 1.3 transport,
    writing them as PEM files to the provided paths. Returns the cert's SHA-256 fingerprint.
    """
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.parent.mkdir(parents=True, exist_ok=True)

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DualDesk Secure Display"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            x509.NameAttribute(NameOID.USER_ID, device_id[:16]),
        ]
    )

    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.DNSName("dualdesk.local"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    cert_path.write_bytes(cert_pem)
    key_path.write_bytes(key_pem)

    cert_der = cert.public_bytes(serialization.Encoding.DER)
    return compute_cert_fingerprint(cert_der)


def get_or_create_tls_credentials(
    storage_dir: Path,
    device_id: str,
) -> tuple[Path, Path, str]:
    """
    Retrieves or generates TLS credentials stored in the application data directory.
    Returns (cert_path, key_path, cert_fingerprint).
    """
    tls_dir = storage_dir / "tls"
    cert_path = tls_dir / "dualdesk_cert.pem"
    key_path = tls_dir / "dualdesk_key.pem"

    if cert_path.is_file() and key_path.is_file():
        try:
            cert_bytes = cert_path.read_bytes()
            cert = x509.load_pem_x509_certificate(cert_bytes)
            now = datetime.datetime.now(datetime.UTC)
            if cert.not_valid_after_utc > now:
                cert_der = cert.public_bytes(serialization.Encoding.DER)
                return cert_path, key_path, compute_cert_fingerprint(cert_der)
        except (ValueError, OSError) as exc:
            logger.warning("Existing TLS credentials invalid or expired, regenerating: %s", exc)

    fingerprint = generate_self_signed_cert(cert_path, key_path, device_id)
    return cert_path, key_path, fingerprint


def create_tls_server_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    """Creates a TLS server SSLContext enforcing TLS 1.3."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return context


def create_tls_client_context() -> ssl.SSLContext:
    """
    Creates a TLS client SSLContext enforcing TLS 1.3.
    Peer certificates are validated post-handshake via cryptographic identity fingerprint pinning.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def verify_peer_certificate(ssl_sock: ssl.SSLSocket, expected_fingerprint: str) -> bool:
    """
    Verifies that the peer certificate presented during the TLS handshake
    cryptographically matches the expected SHA-256 fingerprint.
    """
    if not hasattr(ssl_sock, "getpeercert"):
        return False
    peer_der = ssl_sock.getpeercert(binary_form=True)
    if not peer_der:
        return False
    actual_fingerprint = compute_cert_fingerprint(peer_der)
    return hmac.compare_digest(actual_fingerprint.upper(), expected_fingerprint.upper())
