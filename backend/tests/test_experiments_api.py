"""Experiment-job HTTP lifecycle tests; the child process is faked, never trained."""
import time
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from app.api import experiments as routes
from app.core.config import Settings, get_settings
from app.main import app
from app.services.jobs import ExperimentJobs

PROJECT = "demo-neuroroute"


def auth() -> dict[str, str]:
    now = int(time.time())
    token = jwt.encode({"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "job-user",
                        "iat": now, "exp": now + 3600, "role": "researcher"}, None, algorithm="none")
    return {"Authorization": f"Bearer {token}"}


class Process:
    def __init__(self) -> None:
        self.code: int | None = None
        self.terminated = False

    def poll(self) -> int | None:
        return self.code

    def terminate(self) -> None:
        self.terminated, self.code = True, -15


class Popen:
    def __init__(self) -> None:
        self.processes: list[Process] = []
        self.commands: list[tuple[str, ...]] = []

    def __call__(self, command, **_) -> Process:
        self.commands.append(command)
        process = Process()
        self.processes.append(process)
        return process


@pytest.fixture
def client(tmp_path: Path):
    popen = Popen()
    settings = Settings(training_python=tmp_path / "python.exe", training_jobs_dir=tmp_path / "jobs", max_training_seeds=5,
                        max_training_path_count=8)
    jobs = ExperimentJobs(settings, popen=popen)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[routes.get_jobs] = lambda: jobs
    yield TestClient(app), popen
    app.dependency_overrides.clear()


def test_start_poll_and_prevent_overlap(client) -> None:
    http, popen = client
    created = http.post("/experiments/train", json={"timesteps": 8, "max_episodes": 1, "path_count": 4}, headers=auth())
    assert created.status_code == 202, created.text
    job_id = created.json()["job_id"]
    assert created.json()["status"] == "running"
    assert popen.commands[0][0:3] == (str(popen.commands[0][0]), "-m", "research.training.cli")
    assert "--env-config" in popen.commands[0] and "--output-dir" in popen.commands[0]
    assert http.post("/experiments/train", json={}, headers=auth()).status_code == 400
    popen.processes[0].code = 0
    assert http.get(f"/experiments/{job_id}", headers=auth()).json()["status"] == "done"


def test_cancel_and_reject_over_budget_requests(client) -> None:
    http, popen = client
    created = http.post("/experiments/train", json={}, headers=auth())
    job_id = created.json()["job_id"]
    cancelled = http.post(f"/experiments/{job_id}/cancel", headers=auth())
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert popen.processes[0].terminated
    for body in ({"seed_count": 6}, {"max_episodes": 1001}, {"path_count": 9}, {"timesteps": 100_001}):
        response = http.post("/experiments/train", json=body, headers=auth())
        assert response.status_code == 400, response.text


def test_timeout_terminates_the_child(client) -> None:
    http, popen = client
    created = http.post("/experiments/train", json={}, headers=auth())
    job_id = created.json()["job_id"]
    jobs = app.dependency_overrides[routes.get_jobs]()
    jobs._jobs[job_id].created_at -= jobs.settings.training_timeout_s + 1
    timed_out = http.get(f"/experiments/{job_id}", headers=auth())
    assert timed_out.json() == {"job_id": job_id, "status": "failed", "error": "training exceeded the server timeout"}
    assert popen.processes[0].terminated
