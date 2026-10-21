import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


def test_health_ok() -> None:
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_defaults_are_loopback() -> None:
    assert Settings().host == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.5"])
def test_rejects_non_loopback_host(host: str) -> None:
    with pytest.raises(ValidationError):
        Settings(host=host)


def test_rejects_bad_port() -> None:
    with pytest.raises(ValidationError):
        Settings(port=80)
