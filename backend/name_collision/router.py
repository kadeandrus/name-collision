"""
FastAPI router for name collision endpoints.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .data_importer import import_all
from .service import CACHE, estimate_name_collision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/name-collision", tags=["name-collision"])

# --- Schemas ---
class EstimateRequest(BaseModel):
    first_name: str = ""
    last_name: str = ""
    gender: Optional[str] = None  # "M" | "F" | None


class BatchCustomer(BaseModel):
    id: str
    first_name: str = ""
    last_name: str = ""
    gender: Optional[str] = None


class BatchRequest(BaseModel):
    customers: List[BatchCustomer] = Field(default_factory=list)


# Track an import running in the background to prevent duplicates
_import_lock = asyncio.Lock()
_import_state: dict[str, Any] = {"running": False, "last_result": None, "last_error": None}


# --- Endpoints ---
@router.post("/estimate")
async def estimate_endpoint(payload: EstimateRequest):
    if not CACHE.loaded:
        raise HTTPException(
            status_code=503,
            detail="Name datasets not loaded yet. Try /api/name-collision/import.",
        )
    return estimate_name_collision(
        payload.first_name, payload.last_name, payload.gender
    )


@router.post("/batch")
async def batch_endpoint(payload: BatchRequest):
    if not CACHE.loaded:
        raise HTTPException(
            status_code=503,
            detail="Name datasets not loaded yet. Try /api/name-collision/import.",
        )
    results = []
    for c in payload.customers:
        est = estimate_name_collision(c.first_name, c.last_name, c.gender)
        results.append(
            {
                "id": c.id,
                "first_name": est["first_name"],
                "last_name": est["last_name"],
                "gender_used": est["gender_used"],
                "first_name_population": est["first_name_population"],
                "last_name_population": est["last_name_population"],
                "estimated_us_matches": est["estimated_us_matches"],
                "full_name_collision_risk": est["full_name_collision_risk"],
                "confidence_penalty": est["confidence_penalty"],
                "nickname_canonical": est["nickname_canonical"],
                "warnings": est["warnings"],
            }
        )
    return {"results": results}


@router.get("/stats")
async def stats_endpoint():
    return {
        "loaded": CACHE.loaded,
        "first_name_count": len(CACHE.first_names),
        "last_name_count": len(CACHE.last_names),
        "meta": CACHE.meta,
        "import_running": _import_state["running"],
        "last_import_error": _import_state["last_error"],
    }


async def _run_import_bg(db) -> None:
    from .data_importer import import_all as _import_all

    async with _import_lock:
        _import_state["running"] = True
        _import_state["last_error"] = None
        try:
            summary = await _import_all(db)
            await CACHE.load_from_db(db)
            _import_state["last_result"] = summary
            logger.info("Name collision import complete: %s", summary)
        except Exception as e:  # noqa: BLE001
            logger.exception("Name collision import failed")
            _import_state["last_error"] = str(e)
        finally:
            _import_state["running"] = False


@router.post("/import")
async def import_endpoint():
    from server import db as _db

    if _import_state["running"]:
        return {"status": "already_running"}
    # Fire-and-forget background task; returns immediately
    asyncio.create_task(_run_import_bg(_db))
    return {"status": "started"}


@router.post("/import/sync")
async def import_sync_endpoint():
    """Synchronous import (for tests/admin). May take several minutes."""
    from server import db as _db

    if _import_state["running"]:
        return {"status": "already_running"}
    _import_state["running"] = True
    _import_state["last_error"] = None
    try:
        summary = await import_all(_db)
        await CACHE.load_from_db(_db)
        _import_state["last_result"] = summary
        return {"status": "ok", "summary": summary}
    except Exception as e:  # noqa: BLE001
        logger.exception("Sync import failed")
        _import_state["last_error"] = str(e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        _import_state["running"] = False
