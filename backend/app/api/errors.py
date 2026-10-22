"""Maps domain errors to HTTP so route functions only delegate. Bodies are `{"detail": {code, message, ...}}`."""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.repositories.topologies import StorageError
from app.schemas.topology_api import ErrorBody, ErrorResponse
from app.services.topologies import TopologyInvalid, TopologyNotFound, VersionConflict

log = logging.getLogger("neuroroute.api")


def _json(code: int, body: ErrorBody) -> JSONResponse:
    return JSONResponse(status_code=code, content=ErrorResponse(detail=body).model_dump(mode="json"))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _malformed(_: Request, e: RequestValidationError) -> JSONResponse:
        # FastAPI's default echoes the offending input, which crashes the response for NaN/Infinity (a 500) and
        # reflects arbitrary request data back. Keep only where and why.
        detail = [{"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in e.errors()[:50]]
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content={"detail": detail})

    @app.exception_handler(TopologyInvalid)
    async def _invalid(_: Request, e: TopologyInvalid) -> JSONResponse:
        return _json(status.HTTP_400_BAD_REQUEST, ErrorBody(
            code="invalid_topology", message=f"the topology is not valid ({len(e.reasons)} problem(s))", reasons=e.reasons))

    @app.exception_handler(TopologyNotFound)
    async def _missing(_: Request, __: TopologyNotFound) -> JSONResponse:
        return _json(status.HTTP_404_NOT_FOUND, ErrorBody(code="topology_not_found", message="no such topology"))

    @app.exception_handler(VersionConflict)
    async def _conflict(_: Request, e: VersionConflict) -> JSONResponse:
        return _json(status.HTTP_409_CONFLICT, ErrorBody(
            code="version_conflict", message="the topology changed; reload it and apply your edit again",
            current_version=e.current_version))

    @app.exception_handler(StorageError)
    async def _storage(_: Request, e: StorageError) -> JSONResponse:
        log.error("storage failure: %s", e)  # details stay in the log, not in the response
        return _json(status.HTTP_503_SERVICE_UNAVAILABLE, ErrorBody(
            code="storage_unavailable", message="the topology store is unavailable; try again"))
