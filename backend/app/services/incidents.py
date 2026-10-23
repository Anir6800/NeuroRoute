"""Local, explicit incident records for the NetMind MVP."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from threading import Lock
from uuid import uuid4

__all__ = ["Incident", "IncidentService"]


@dataclass(frozen=True)
class Incident:
    id: str
    created_at: str
    severity: str
    title: str
    diagnosis: str
    evidence: tuple[str, ...]
    timeline: tuple[str, ...]

    def out(self) -> dict[str, object]:
        return asdict(self)


class IncidentService:
    """Process-local incident store; callers provide all evidence and diagnosis explicitly."""

    def __init__(self) -> None:
        self._items: dict[str, Incident] = {}
        self._lock = Lock()

    def trigger(self, *, severity: str, title: str, diagnosis: str, evidence: tuple[str, ...]) -> Incident:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        incident = Incident(uuid4().hex, now, severity, title, diagnosis, evidence, (f"{now}: incident triggered",))
        with self._lock:
            self._items[incident.id] = incident
        return incident

    def list(self) -> list[Incident]:
        with self._lock:
            return sorted(self._items.values(), key=lambda incident: incident.created_at, reverse=True)

    def get(self, incident_id: str) -> Incident | None:
        with self._lock:
            return self._items.get(incident_id)
