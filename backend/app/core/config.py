from functools import lru_cache
from ipaddress import ip_address

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NEUROROUTE_", env_file=".env", extra="ignore")

    app_name: str = "NeuroRoute"
    version: str = "0.1.0"
    host: str = "127.0.0.1"
    port: int = Field(default=8001, ge=1024, le=65535)

    @field_validator("host")
    @classmethod
    def host_must_be_loopback(cls, v: str) -> str:
        # Local-only MVP: refuse to bind anything but loopback.
        if v != "localhost" and not ip_address(v).is_loopback:
            raise ValueError("host must be a loopback address")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
