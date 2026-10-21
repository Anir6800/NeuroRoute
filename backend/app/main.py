from fastapi import FastAPI

from app.api import me
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(me.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "version": settings.version}
