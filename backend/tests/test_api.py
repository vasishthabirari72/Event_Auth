from event_auth.api.app import create_app
from fastapi.testclient import TestClient


def test_health_and_readiness_are_distinct():
    client = TestClient(create_app(readiness=lambda: False))
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/ready").status_code == 503
    assert TestClient(create_app(readiness=lambda: True)).get("/api/ready").status_code == 200


def test_built_frontend_and_unknown_api(tmp_path):
    (tmp_path / "index.html").write_text("<html>local</html>")
    client = TestClient(create_app(frontend=tmp_path))
    assert client.get("/").status_code == 200
    assert client.get("/api/not-real").status_code == 404
    assert client.get("/docs").status_code == 404
