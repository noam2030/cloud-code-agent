import asyncio
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field

from app import agents, store, workspace

log = logging.getLogger(__name__)
MAX_ROUNDS = 2
TERMINAL = {"answered", "awaiting_approval", "done", "rejected", "failed"}
LOCK = asyncio.Lock()  # one git operation on the workspace at a time
RUNS: dict[str, "Run"] = {}


@dataclass
class Run:
    message: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "running"
    events: list[dict] = field(default_factory=list)
    proposal: dict | None = None
    branch: str | None = None
    pr_url: str | None = None
    started: float = field(default_factory=time.time)
    stats: dict = field(
        default_factory=lambda: {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "tool_calls": 0}
    )

    def emit(self, type_: str, **data) -> None:
        self.events.append({"type": type_, "t": round(time.time() - self.started, 2), **data})

    def count_llm(self, usage) -> None:
        self.stats["llm_calls"] += 1
        if usage:
            self.stats["input_tokens"] += usage.get("input_tokens", 0)
            self.stats["output_tokens"] += usage.get("output_tokens", 0)

    def to_dict(self) -> dict:
        return {**asdict(self), "duration_s": round(time.time() - self.started, 2)}

    @classmethod
    def from_dict(cls, doc: dict) -> "Run":
        keys = ("id", "message", "status", "events", "proposal", "branch", "pr_url", "stats")
        return cls(
            **{k: doc[k] for k in keys if k in doc},
            started=time.time() - doc.get("duration_s", 0),
        )


async def load(run_id: str) -> Run | None:
    """Return a run from memory, or rebuild it from Firestore if another instance handled it."""
    run = RUNS.get(run_id)
    if run is None:
        doc = await store.load(run_id)
        if doc is None:
            return None
        run = Run.from_dict(doc)
        RUNS[run_id] = run
    return run


async def execute(run: Run) -> None:
    """Route the request to the Answerer, or to the Writer/Reviewer loop."""
    try:
        route, usage = await agents.route(run.message)
        run.count_llm(usage)
        run.emit("route", intent=route.intent)
        context = await asyncio.to_thread(workspace.snapshot)
        run.stats["tool_calls"] += 1

        if route.intent == "answer":
            text, usage = await agents.answer(run.message, context)
            run.count_llm(usage)
            run.emit("answer", text=text)
            run.status = "answered"
            return

        review_text = None
        for round_no in range(1, MAX_ROUNDS + 1):
            proposal, usage = await agents.write(run.message, context, review_text)
            run.count_llm(usage)
            run.emit("proposal", round=round_no, summary=proposal.summary,
                     files=[f.path for f in proposal.files])

            review_text, usage = await agents.review(run.message, proposal)
            run.count_llm(usage)
            approved = review_text.strip().upper().startswith("APPROVE")
            run.emit("review", round=round_no, approved=approved, text=review_text)
            if approved:
                break

        run.proposal = proposal.model_dump()
        run.status = "awaiting_approval"
        run.emit("awaiting_approval")
    except Exception as e:
        log.exception("run %s failed", run.id)
        run.status = "failed"
        run.emit("error", text=str(e))
    finally:
        await store.save(run)


async def apply(run: Run) -> None:
    """Called only after the user approves: push a side branch and open a PR."""
    try:
        run.branch = f"agent/{run.id}"
        run.emit("status", text=f"pushing {run.branch} and opening PR")
        async with LOCK:
            run.pr_url = await asyncio.to_thread(
                workspace.commit_and_pr, run.branch, run.proposal, run.message
            )
        run.stats["tool_calls"] += 1
        run.status = "done"
        run.emit("pr", url=run.pr_url)
    except Exception as e:
        log.exception("apply for run %s failed", run.id)
        run.status = "failed"
        run.emit("error", text=str(e))
    finally:
        await store.save(run)
