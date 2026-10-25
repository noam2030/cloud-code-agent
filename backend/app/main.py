import asyncio
import json

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app import config, orchestrator, store
from app.auth import current_user
from app.orchestrator import RUNS, TERMINAL, Run

app = FastAPI(title="cloud-code-agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)


class NewRun(BaseModel):
    message: str = Field(min_length=1, max_length=8000)


def _get_run(run_id: str) -> Run:
    run = RUNS.get(run_id)
    if run is None:
        raise HTTPException(404, "unknown run")
    return run


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/runs")
async def create_run(body: NewRun, user: str = Depends(current_user)):
    run = Run(message=body.message)
    RUNS[run.id] = run
    asyncio.create_task(orchestrator.execute(run))
    return {"id": run.id}


@app.get("/runs/{run_id}")
def get_run(run_id: str, user: str = Depends(current_user)):
    return _get_run(run_id).to_dict()


@app.get("/runs/{run_id}/events")
async def stream_events(run_id: str, user: str = Depends(current_user)):
    run = _get_run(run_id)

    async def stream():
        sent = 0
        while True:
            while sent < len(run.events):
                yield f"data: {json.dumps(run.events[sent])}\n\n"
                sent += 1
            if run.status in TERMINAL:
                break
            await asyncio.sleep(0.5)
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/runs/{run_id}/approve")
async def approve_run(run_id: str, user: str = Depends(current_user)):
    run = _get_run(run_id)
    if run.status != "awaiting_approval":
        raise HTTPException(409, f"run is {run.status}")
    run.status = "applying"
    asyncio.create_task(orchestrator.apply(run))
    return {"status": run.status}


@app.post("/runs/{run_id}/reject")
async def reject_run(run_id: str, user: str = Depends(current_user)):
    run = _get_run(run_id)
    if run.status != "awaiting_approval":
        raise HTTPException(409, f"run is {run.status}")
    run.status = "rejected"
    run.emit("rejected")
    await store.save(run)
    return {"status": run.status}
