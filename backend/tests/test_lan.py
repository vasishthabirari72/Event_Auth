import ipaddress
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from event_auth.adapters.backup import write_private
from event_auth.operations.lan import validate_tls
from test_m2 import system  # noqa: F401


@pytest.fixture
def tls_files(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test localhost certificate")])
    current = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(current - timedelta(minutes=1))
        .not_valid_after(current + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "test.pem", tmp_path / "test.key"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    write_private(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    return cert_path, key_path


def test_tls_requires_matching_san_private_key_and_local_ip(tls_files):
    cert, key = tls_files
    assert validate_tls("127.0.0.1", 8443, cert, key) == "https://127.0.0.1:8443"
    for host in ["0.0.0.0", "8.8.8.8", "192.168.1.22"]:
        with pytest.raises(ValueError):
            validate_tls(host, 8443, cert, key)
    key.chmod(0o644)
    with pytest.raises(ValueError, match="0600"):
        validate_tls("127.0.0.1", 8443, cert, key)


@pytest.mark.postgres
def test_real_https_login_cookie_origin_and_host(system, tls_files, monkeypatch):  # noqa: F811
    import socket
    import ssl
    import threading
    import time

    import httpx
    import uvicorn
    from event_auth.api.app import create_app

    _, factory, vault, _ = system
    cert, key = tls_files
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    origin = "https://127.0.0.1:" + str(listener.getsockname()[1])
    monkeypatch.setenv("EVENT_AUTH_COOKIE_SECURE", "true")
    monkeypatch.setenv("EVENT_AUTH_HOSTS", "127.0.0.1")
    monkeypatch.setenv("EVENT_AUTH_ORIGINS", origin)
    app = create_app(readiness=lambda: True, sessions=factory, vault=vault)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            ssl_certfile=str(cert),
            ssl_keyfile=str(key),
            access_log=False,
            proxy_headers=False,
            log_level="error",
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started
        with httpx.Client(
            base_url=origin, verify=ssl.create_default_context(cafile=str(cert)), trust_env=False
        ) as client:
            assert client.get("/api/ready").status_code == 200
            assert client.get("/api/counter/events").status_code == 401
            assert (
                client.get("/api/ready", headers={"Host": "untrusted.example"}).status_code == 400
            )
            body = {"username": "test_admin", "pin": "123456"}
            assert (
                client.post(
                    "/api/auth/login", json=body, headers={"Origin": "https://untrusted.example"}
                ).status_code
                == 403
            )
            login = client.post("/api/auth/login", json=body, headers={"Origin": origin})
            assert login.status_code == 200
            cookie = login.headers["set-cookie"].lower()
            assert "secure" in cookie and "httponly" in cookie and "samesite=strict" in cookie
            assert client.get("/api/counter/events").status_code == 200
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        listener.close()
        assert not thread.is_alive()
