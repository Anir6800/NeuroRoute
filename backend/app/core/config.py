from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _check_loopback(host: str) -> str:
    # Local-only MVP: refuse to bind or talk to anything but loopback.
    if host != "localhost" and not ip_address(host).is_loopback:
        raise ValueError("host must be a loopback address")
    return host


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEUROROUTE_", env_file=".env", extra="ignore")

    app_name: str = "NeuroRoute"
    version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = Field(default=8001, ge=1024, le=65535)
    # Firebase Auth EMULATOR only. "demo-" projects can never be real Firebase projects.
    firebase_project_id: str = Field(default="demo-neuroroute", pattern=r"^demo-[a-z0-9-]+$")
    auth_emulator_host: str = "127.0.0.1:9099"
    allowed_roles: tuple[str, ...] = ("researcher", "admin")
    # Topology API: local SQLite file (git-ignored) and size limits that bound request cost.
    db_path: Path = Path(__file__).resolve().parents[2] / ".data" / "neuroroute.sqlite3"
    db_timeout_s: float = Field(default=5.0, gt=0, le=60)
    max_topology_nodes: int = Field(default=64, ge=2, le=10_000)
    max_topology_links: int = Field(default=512, ge=1, le=100_000)

    @field_validator("host")
    @classmethod
    def host_must_be_loopback(cls, v: str) -> str:
        return _check_loopback(v)

    @field_validator("auth_emulator_host")
    @classmethod
    def emulator_must_be_loopback(cls, v: str) -> str:
        host, sep, port = v.rpartition(":")
        if not sep or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError("auth_emulator_host must look like host:port")
        _check_loopback(host)
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
