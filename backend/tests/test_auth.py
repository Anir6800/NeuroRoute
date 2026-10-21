"""Auth tests use unsigned emulator-style tokens through the real firebase-admin code path."""
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app

PROJECT = "demo-neuroroute"
client = TestClient(app)


def token(**over) -> str:
    now = int(time.time())
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT}",
        "aud": PROJECT,
        "sub": "uid-1",
        "email": "dev@neuroroute.test",
        "iat": now,
        "exp": now + 3600,
        "role": "researcher",
    }
    claims.update(over)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, None, algorithm="none")


def get_me(tok: str | None = None, header: str | None = None):
    headers = {}
    if tok is not None:
        headers["Authorization"] = f"Bearer {tok}"
    if header is not None:
        headers["Authorization"] = header
    return client.get("/me", headers=headers)


def test_valid_token_returns_user() -> None:
    r = get_me(token())
    assert r.status_code == 200
    assert r.json() == {"uid": "uid-1", "email": "dev@neuroroute.test", "role": "researcher"}


def test_admin_role_allowed() -> None:
    assert get_me(token(role="admin")).status_code == 200


def test_missing_token_is_401() -> None:
    r = client.get("/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer not.a.jwt"])
def test_malformed_credentials_are_401_or_403_never_200(header: str) -> None:
    assert get_me(header=header).status_code in (401, 403)


def test_garbage_bearer_is_401() -> None:
    assert get_me("not-a-jwt").status_code == 401


def test_expired_token_is_401() -> None:
    past = int(time.time()) - 3600
    assert get_me(token(exp=past, iat=past - 60)).status_code == 401


def test_missing_exp_is_401() -> None:
    assert get_me(token(exp=None)).status_code == 401


def test_wrong_project_is_403() -> None:
    r = get_me(token(aud="demo-other", iss="https://securetoken.google.com/demo-other"))
    assert r.status_code == 403


def test_wrong_role_is_403() -> None:
    assert get_me(token(role="guest")).status_code == 403


def test_missing_role_is_403() -> None:
    assert get_me(token(role=None)).status_code == 403


def test_health_stays_public() -> None:
    assert client.get("/health").status_code == 200


@pytest.mark.parametrize("kw", [{"firebase_project_id": "real-project"}, {"auth_emulator_host": "0.0.0.0:9099"},
                                {"auth_emulator_host": "example.com:9099"}, {"auth_emulator_host": "127.0.0.1"}])
def test_settings_refuse_non_emulator_config(kw: dict) -> None:
    with pytest.raises(ValidationError):
        Settings(**kw)
