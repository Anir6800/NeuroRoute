"""WebSocket progress events for local experiment jobs."""
from __future__ import annotations

import asyncio
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.api.experiments import get_jobs
from app.core.auth import verify_token
from app.core.config import Settings, get_settings
from app.services.jobs import ExperimentJobs

router = APIRouter(prefix="/events", tags=["events"])
TERMINAL = {"cancelled", "failed", "done"}


@router.websocket("/experiments/{job_id}")
async def experiment_events(
    websocket: WebSocket,
    job_id: str,
    jobs: Annotated[ExperimentJobs, Depends(get_jobs)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    await websocket.accept()
    try:
        auth = await asyncio.wait_for(websocket.receive_json(), timeout=5)
        token = auth.get("token") if isinstance(auth, dict) else None
        if not isinstance(token, str):
            raise TypeError
        verify_token(token, settings)
    except WebSocketDisconnect:
        return
    except (TimeoutError, TypeError, HTTPException):
        await websocket.close(code=4401, reason="Authentication required")
        return

    try:
        while True:
            progress = jobs.progress(job_id)
            if progress is None:
                await websocket.close(code=4404, reason="No such training job")
                return
            await websocket.send_json(progress)
            if progress["status"] in TERMINAL:
                await websocket.close()
                return
            await websocket.send_json({"type": "heartbeat", "timestamp": time.time()})
            await asyncio.sleep(settings.training_event_interval_s)
    except WebSocketDisconnect:
        return
