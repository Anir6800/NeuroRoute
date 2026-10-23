"""Live local incident endpoint tests."""
import time

import jwt
from fastapi.testclient import TestClient

from app.api.incidents import get_incidents
from app.main import app
from app.services.incidents import IncidentService

PROJECT = "demo-neuroroute"


def _auth() -> dict[str, str]:
    now = int(time.time())
    token = jwt.encode({"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "incident-user",
                        "iat": now, "exp": now + 3600, "role": "researcher"}, None, algorithm="none")
    return {"Authorization": f"Bearer {token}"}


def test_trigger_list_and_detail_are_live() -> None:
    service = IncidentService()
    app.dependency_overrides[get_incidents] = lambda: service
    try:
        with TestClient(app) as client:
            created = client.post("/incidents/trigger", headers=_auth(), json={
                "title": "Packet loss observed", "severity": "warning", "diagnosis": "Manual test diagnosis.",
                "evidence": ["Loss exceeded the local threshold."],
            })
            assert created.status_code == 201, created.text
            incident = created.json()
            assert client.get("/incidents", headers=_auth()).json() == [incident]
            assert client.get(f"/incidents/{incident['id']}", headers=_auth()).json() == incident
    finally:
        app.dependency_overrides.clear()
