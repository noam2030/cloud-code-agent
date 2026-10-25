import asyncio
import logging

from google.cloud import firestore

from app import config

log = logging.getLogger(__name__)
_db = None


def _runs():
    global _db
    if _db is None:
        _db = firestore.Client(project=config.GCP_PROJECT)
    return _db.collection("agent_runs")


async def save(run) -> None:
    """Persist run status, events and usage stats for observability."""
    try:
        doc = run.to_dict()
        doc["updated_at"] = firestore.SERVER_TIMESTAMP
        await asyncio.to_thread(_runs().document(run.id).set, doc)
    except Exception:
        log.exception("failed to save run %s", run.id)
