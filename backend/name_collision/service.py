"""
In-memory cache + estimation logic for name collision scoring.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .data_importer import (
    classify_first_name_risk,
    classify_last_name_risk,
    normalize_name,
)
from .nickname_map import canonical_first_name

logger = logging.getLogger(__name__)

US_POPULATION = 330_000_000

DATA_SOURCES = ["SSA Baby Names", "U.S. Census 2010 Surnames"]

FORMULA = "(first_name_population * last_name_population) / 330000000"

CAVEAT = (
    "estimated_us_matches is a statistical estimate based on independent "
    "first-name and last-name frequency. It should be used as a collision-risk "
    "signal, not an exact population count."
)


class NameCache:
    """Loaded once at startup from MongoDB."""

    def __init__(self) -> None:
        # first_names[name] = { "M": {...}, "F": {...} }
        self.first_names: dict[str, dict[str, dict[str, Any]]] = {}
        # last_names[name] = {...}
        self.last_names: dict[str, dict[str, Any]] = {}
        self.meta: dict[str, Any] = {}
        self.loaded: bool = False

    async def load_from_db(self, db) -> None:
        fn_map: dict[str, dict[str, dict[str, Any]]] = {}
        cursor = db.first_name_stats.find({}, {"_id": 0})
        async for row in cursor:
            n = row["name_normalized"]
            g = row["gender"]
            fn_map.setdefault(n, {})[g] = {
                "total_count": int(row["total_count"]),
                "rank": row.get("rank"),
                "risk_level": row.get("risk_level")
                or classify_first_name_risk(row.get("rank")),
            }

        ln_map: dict[str, dict[str, Any]] = {}
        cursor = db.last_name_stats.find({}, {"_id": 0})
        async for row in cursor:
            n = row["name_normalized"]
            ln_map[n] = {
                "total_count": int(row["total_count"]),
                "rank": row.get("rank"),
                "proportion_per_100k": row.get("proportion_per_100k"),
                "risk_level": row.get("risk_level")
                or classify_last_name_risk(row.get("rank")),
            }

        meta = await db.name_collision_meta.find_one(
            {"_kind": "name_collision_import"}, {"_id": 0}
        )

        self.first_names = fn_map
        self.last_names = ln_map
        self.meta = meta or {}
        self.loaded = True
        logger.info(
            "NameCache loaded: %d first names, %d last names",
            len(fn_map),
            len(ln_map),
        )

    def is_empty(self) -> bool:
        return not self.first_names and not self.last_names


# Singleton
CACHE = NameCache()


def _penalty_for(risk: str) -> float:
    return {"high": 0.45, "medium": 0.25, "low": 0.05}.get(risk, 0.25)


def _full_name_risk(estimate: Optional[float]) -> str:
    if estimate is None:
        return "unknown"
    if estimate >= 1000:
        return "high"
    if estimate >= 100:
        return "medium"
    return "low"


def _is_initial(s: str) -> bool:
    """True if input looks like a single initial, e.g. 'J' or 'J.'"""
    stripped = re.sub(r"[^\w]", "", s or "")
    return len(stripped) == 1


def _lookup_first_name(
    cache: NameCache, n: str, gender: Optional[str]
) -> tuple[Optional[dict], Optional[str], Optional[float]]:
    """
    Returns (stats_dict_for_chosen_gender, gender_used, gender_confidence).
    If gender is provided, it is used directly.
    Otherwise the gender with the largest total_count wins.
    """
    entry = cache.first_names.get(n)
    if not entry:
        return None, None, None

    if gender:
        g = gender.upper()
        if g in entry:
            return entry[g], g, 1.0
        # Requested gender missing; fall through to dominant
    # Pick dominant
    total = sum(v["total_count"] for v in entry.values()) or 1
    g_dom, stats = max(entry.items(), key=lambda kv: kv[1]["total_count"])
    conf = round(stats["total_count"] / total, 3)
    return stats, g_dom, conf


def _split_hyphenated(last_norm: str) -> list[str]:
    if "-" not in last_norm:
        return [last_norm]
    parts = [p.strip() for p in last_norm.split("-") if p.strip()]
    return parts or [last_norm]


def estimate_name_collision(
    first_name: str,
    last_name: str,
    gender: Optional[str] = None,
    *,
    cache: NameCache = CACHE,
) -> dict[str, Any]:
    """
    Main estimation function. Returns the structured JSON response described
    in the spec. Handles nicknames, hyphenated last names, initials, missing
    data, and unknown names.
    """
    first_raw = (first_name or "").strip()
    last_raw = (last_name or "").strip()

    first_norm = normalize_name(first_raw)
    last_norm = normalize_name(last_raw)

    result: dict[str, Any] = {
        "first_name": first_raw,
        "last_name": last_raw,
        "first_name_normalized": first_norm or None,
        "last_name_normalized": last_norm or None,
        "gender_used": None,
        "gender_confidence": None,
        "first_name_population": None,
        "first_name_risk_level": "unknown",
        "last_name_population": None,
        "last_name_rank": None,
        "last_name_proportion_per_100k": None,
        "last_name_risk_level": "unknown",
        "estimated_us_matches": None,
        "full_name_collision_risk": "unknown",
        "confidence_penalty": _penalty_for("medium"),
        "formula": FORMULA,
        "data_sources": DATA_SOURCES,
        "nickname_canonical": None,
        "alternate_estimate_for_canonical": None,
        "warnings": [],
        "caveat": CAVEAT,
    }

    # Missing inputs
    if not first_norm:
        result["warnings"].append("missing_first_name")
    if not last_norm:
        result["warnings"].append("missing_last_name")
    if not first_norm or not last_norm:
        return result

    # Initial-only first name
    if _is_initial(first_raw):
        result["warnings"].append("first_name_is_initial_high_uncertainty")

    # --- First name lookup (with nickname support) ---
    fn_stats, gender_used, gender_conf = _lookup_first_name(
        cache, first_norm, gender
    )
    canonical = canonical_first_name(first_norm)
    canonical_stats = None
    canonical_gender = None
    canonical_gc = None

    if canonical and canonical != first_norm:
        canonical_stats, canonical_gender, canonical_gc = _lookup_first_name(
            cache, canonical, gender
        )
        result["nickname_canonical"] = canonical
        # If the raw input wasn't found, use canonical as primary
        if fn_stats is None and canonical_stats is not None:
            fn_stats = canonical_stats
            gender_used = canonical_gender
            gender_conf = canonical_gc
            result["warnings"].append("resolved_via_nickname_map")

    if fn_stats:
        result["first_name_population"] = fn_stats["total_count"]
        result["first_name_risk_level"] = fn_stats.get("risk_level", "unknown")
        result["gender_used"] = gender_used
        result["gender_confidence"] = gender_conf
    else:
        result["warnings"].append("first_name_not_found")

    # --- Last name lookup (with hyphenated handling) ---
    ln_parts = _split_hyphenated(last_norm)
    per_part_stats: list[dict[str, Any]] = []
    for p in ln_parts:
        stats = cache.last_names.get(p)
        per_part_stats.append(
            {
                "part": p,
                "population": stats["total_count"] if stats else None,
                "rank": stats["rank"] if stats else None,
                "risk_level": stats["risk_level"] if stats else "unknown",
            }
        )

    # Primary last-name stats: first part if found, else any found part, else None
    primary_ln = None
    for ps in per_part_stats:
        if ps["population"] is not None:
            primary_ln = ps
            break

    if primary_ln:
        result["last_name_population"] = primary_ln["population"]
        result["last_name_rank"] = primary_ln["rank"]
        result["last_name_risk_level"] = primary_ln["risk_level"]
        full_stats = cache.last_names.get(primary_ln["part"])
        if full_stats:
            result["last_name_proportion_per_100k"] = full_stats.get(
                "proportion_per_100k"
            )
    else:
        result["warnings"].append("last_name_not_found")

    if len(ln_parts) > 1:
        result["hyphenated_last_name_parts"] = per_part_stats

    # --- Estimate ---
    fpop = result["first_name_population"]
    lpop = result["last_name_population"]
    if fpop and lpop:
        est = (fpop * lpop) / US_POPULATION
        result["estimated_us_matches"] = int(round(est))
        result["full_name_collision_risk"] = _full_name_risk(est)
        result["confidence_penalty"] = _penalty_for(
            result["full_name_collision_risk"]
        )
    else:
        result["estimated_us_matches"] = None
        result["full_name_collision_risk"] = "unknown"
        result["confidence_penalty"] = _penalty_for("medium")

    # --- Alternate estimate using canonical name (if different) ---
    if (
        canonical
        and canonical_stats
        and canonical != first_norm
        and lpop
    ):
        can_pop = canonical_stats["total_count"]
        can_est = (can_pop * lpop) / US_POPULATION
        result["alternate_estimate_for_canonical"] = {
            "canonical_first_name": canonical,
            "first_name_population": can_pop,
            "first_name_risk_level": canonical_stats.get("risk_level"),
            "gender_used": canonical_gender,
            "gender_confidence": canonical_gc,
            "estimated_us_matches": int(round(can_est)),
            "full_name_collision_risk": _full_name_risk(can_est),
            "confidence_penalty": _penalty_for(_full_name_risk(can_est)),
        }

    return result
