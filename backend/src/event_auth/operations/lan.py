"""Explicit LAN HTTPS launcher; default development startup remains localhost-only."""

import argparse
import ipaddress
import os
import ssl
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from cryptography import x509


def validate_tls(host: str, port: int, certificate: Path, key: Path) -> str:
    address = ipaddress.ip_address(host)
    networks = [
        ipaddress.ip_network(value)
        for value in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
    ]
    if not any(address in network for network in networks) or not 1024 <= port <= 65535:
        raise ValueError("Use a specific private IPv4 address and an unprivileged port")
    if key.is_symlink() or not key.is_file() or key.stat().st_mode & 0o077:
        raise ValueError("TLS private key must be a regular 0600 file")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certificate, key)
    cert = x509.load_pem_x509_certificate(certificate.read_bytes())
    current = datetime.now(UTC)
    if not cert.not_valid_before_utc <= current < cert.not_valid_after_utc:
        raise ValueError("TLS certificate is not currently valid")
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    if address not in names.get_values_for_type(x509.IPAddress):
        raise ValueError("TLS certificate must include this server IP address")
    return f"https://{host}:{port}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the local event network using trusted TLS")
    parser.add_argument("--host", required=True, help="Laptop's reserved private IPv4 address")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--cert", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--check", action="store_true", help="Validate without opening a listener")
    args = parser.parse_args()
    try:
        origin = validate_tls(args.host, args.port, args.cert.expanduser(), args.key.expanduser())
        # Override development settings; no wildcard host/origin or forwarded-header trust.
        os.environ["EVENT_AUTH_COOKIE_SECURE"] = "true"
        os.environ["EVENT_AUTH_HOSTS"] = args.host
        os.environ["EVENT_AUTH_ORIGINS"] = origin
        from event_auth.api.app import create_app, database_ready
        from event_auth.face_lab import model_provenance

        root = Path(__file__).resolve().parents[4]
        if not (root / "frontend/dist/index.html").is_file() or not database_ready():
            raise ValueError("Build the UI and start the database before LAN startup")
        model_provenance(root / "assets/models")
        app = create_app()
        if app.state.vault is None or app.state.signer is None:
            raise ValueError("Original encryption and signing keys are required")
        if args.check:
            print("HTTPS configuration valid. Install the CA certificate on each intended device.")
            return
        print("Local event server: " + origin)
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            ssl_certfile=str(args.cert.expanduser()),
            ssl_keyfile=str(args.key.expanduser()),
            ssl_version=ssl.PROTOCOL_TLS_SERVER,
            proxy_headers=False,
            access_log=False,
        )
    except (Exception, KeyboardInterrupt):
        parser.exit(
            1,
            "HTTPS failed. Check address, certificate, key permissions, models and database.\n",
        )


if __name__ == "__main__":
    main()
