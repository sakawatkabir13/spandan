#!/usr/bin/env python3
"""Create private initial mTLS material. Output stays under ignored .runtime/."""

import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


def create(destination, app_ip, mcp_ip):
    root = Path(destination)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if (root / "ca-key.pem").exists():
        raise RuntimeError(
            "Existing CA preserved. Use a reviewed certificate renewal instead of replacing trust."
        )
    now = datetime.now(timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Spandan private services CA")]
    )
    ca = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1095))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(True, False, False, False, False, True, True, False, False),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    def save(path, value):
        path.write_bytes(value)
        path.chmod(0o600)

    save(
        root / "ca-key.pem",
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    for label, address in [("app", app_ip), ("mcp", mcp_ip)]:
        folder = root / label
        folder.mkdir(mode=0o700, exist_ok=True)
        key = ec.generate_private_key(ec.SECP256R1())
        cert = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "spandan-" + label)])
            )
            .issuer_name(ca.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5))
            .not_valid_after(now + timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.IPAddress(ipaddress.ip_address(address))]
                ),
                critical=False,
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None), critical=True
            )
            .add_extension(
                x509.ExtendedKeyUsage(
                    [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]
                ),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256())
        )
        save(folder / "ca.pem", ca.public_bytes(serialization.Encoding.PEM))
        save(folder / "service-cert.pem", cert.public_bytes(serialization.Encoding.PEM))
        save(
            folder / "service-key.pem",
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", default=".runtime/chat-tls")
    parser.add_argument("--app-ip", required=True)
    parser.add_argument("--mcp-ip", required=True)
    options = parser.parse_args()
    create(options.destination, options.app_ip, options.mcp_ip)
