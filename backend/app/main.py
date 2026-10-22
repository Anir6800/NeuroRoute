from fastapi import FastAPI

from app.api import me, topologies
from app.api.errors import register_error_handlers
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.version)
app.include_router(me.router)
app.include_router(topologies.router)
register_error_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "version": settings.version}
