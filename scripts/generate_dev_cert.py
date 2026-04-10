from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


DEFAULT_HOSTS = [
    "prod.egonet.codemasters.com",
    "qa.egonet.codemasters.com",
    "terms.codemasters.com",
    "aurora.codemasters.local",
    "localhost",
]


def write_certificate(cert_path: Path, key_path: Path, hosts: list[str]) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DR2 Community Server"),
            x509.NameAttribute(NameOID.COMMON_NAME, hosts[0]),
        ]
    )

    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(host) for host in hosts]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a local TLS certificate for the DR2 community server.")
    parser.add_argument("--cert", default="runtime/certs/dr2server-cert.pem")
    parser.add_argument("--key", default="runtime/certs/dr2server-key.pem")
    parser.add_argument("--host", action="append", dest="hosts")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    hosts = args.hosts or DEFAULT_HOSTS
    write_certificate(Path(args.cert), Path(args.key), hosts)
    print(f"Generated certificate: {args.cert}")
    print(f"Generated private key: {args.key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
