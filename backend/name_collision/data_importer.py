"""
Download and import official public name datasets:
  - SSA baby names (first-name frequencies by year, gender) — birth years 1941–2010
    (covers ages ~16–85 as of 2026). Source mirror:
    https://raw.githubusercontent.com/hackerb9/ssa-baby-names/main/alldata.txt
    Original: https://www.ssa.gov/oact/babynames/limits.html

  - U.S. Census 2010 surnames (rank, count, proportion). Source:
    https://www2.census.gov/topics/genealogy/2010surnames/names.zip

Data is normalized and written to MongoDB collections:
  - first_name_stats
  - last_name_stats
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

SSA_ALLDATA_URL = (
    "https://raw.githubusercontent.com/hackerb9/ssa-baby-names/main/alldata.txt"
)
CENSUS_2010_SURNAMES_URL = (
    "https://www2.census.gov/topics/genealogy/2010surnames/names.zip"
)

# Ages 16–85 as of 2026 -> birth years 1941..2010 inclusive
SSA_YEAR_MIN = 1941
SSA_YEAR_MAX = 2010


# -------- Normalization --------
_PUNCT_RE = re.compile(r"[^\w\s'-]", flags=re.UNICODE)


def normalize_name(name: str) -> str:
    """Trim, lowercase, strip accents, remove punctuation."""
    if name is None:
        return ""
    s = str(name).strip()
    # strip accents
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    # strip apostrophes entirely (Census data stores e.g. "obrien" not "o'brien")
    s = s.replace("'", "").replace("\u2019", "")
    # remove punctuation except internal hyphens
    s = _PUNCT_RE.sub("", s)
    # collapse internal whitespace
    s = re.sub(r"\s+", " ", s).strip()
    # strip leading/trailing punctuation
    s = s.strip("-")
    return s


# -------- Risk classification --------
def classify_first_name_risk(rank: int | None) -> str:
    if rank is None:
        return "unknown"
    if rank <= 20:
        return "high"
    if rank <= 120:
        return "medium"
    return "low"


def classify_last_name_risk(rank: int | None) -> str:
    if rank is None:
        return "unknown"
    if rank <= 20:
        return "high"
    if rank <= 500:
        return "medium"
    return "low"


# -------- Downloaders --------
def _download_bytes(url: str, timeout: int = 120) -> bytes:
    logger.info("Downloading %s", url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (NameCollisionTool/1.0; "
            "+https://emergent.sh)"
        )
    }
    resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
    resp.raise_for_status()
    return resp.content


# -------- SSA first names --------
def fetch_ssa_first_names() -> list[dict[str, Any]]:
    """
    Returns list of dicts:
      { name_normalized, gender, total_count }
    Aggregated across years SSA_YEAR_MIN..SSA_YEAR_MAX.
    """
    raw = _download_bytes(SSA_ALLDATA_URL).decode("utf-8", errors="replace")
    # alldata.txt format: name,sex,count,year
    agg: dict[tuple[str, str], int] = defaultdict(int)
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != 4:
            continue
        name, sex, count, year = parts
        try:
            year_i = int(year)
            count_i = int(count)
        except ValueError:
            continue
        if year_i < SSA_YEAR_MIN or year_i > SSA_YEAR_MAX:
            continue
        sex = sex.strip().upper()
        if sex not in ("M", "F"):
            continue
        n = normalize_name(name)
        if not n:
            continue
        agg[(n, sex)] += count_i

    # Rank per gender by total_count (desc)
    by_gender: dict[str, list[tuple[str, int]]] = {"M": [], "F": []}
    for (n, g), c in agg.items():
        by_gender[g].append((n, c))
    out: list[dict[str, Any]] = []
    for g, items in by_gender.items():
        items.sort(key=lambda x: (-x[1], x[0]))
        for rank, (n, c) in enumerate(items, start=1):
            out.append(
                {
                    "name_normalized": n,
                    "gender": g,
                    "total_count": c,
                    "rank": rank,
                    "risk_level": classify_first_name_risk(rank),
                }
            )
    logger.info("SSA aggregated %d first-name rows", len(out))
    return out


# -------- Census last names --------
def fetch_census_last_names() -> list[dict[str, Any]]:
    """
    Census 2010 surnames CSV columns (relevant):
      name, rank, count, prop100k (proportion per 100,000)
    """
    raw = _download_bytes(CENSUS_2010_SURNAMES_URL)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        csv_name = next(
            (n for n in zf.namelist() if n.lower().endswith(".csv")), None
        )
        if not csv_name:
            raise RuntimeError("Census ZIP has no CSV")
        with zf.open(csv_name) as f:
            df = pd.read_csv(f, dtype=str, low_memory=False)

    # Normalize column names
    df.columns = [c.strip().lower() for c in df.columns]

    def find_col(*cands: str) -> str:
        for c in cands:
            if c in df.columns:
                return c
        raise RuntimeError(f"Column not found, tried {cands}, have {df.columns.tolist()}")

    name_col = find_col("name", "surname")
    rank_col = find_col("rank")
    count_col = find_col("count")
    prop_col = None
    for c in ("prop100k", "pct100k", "prop_100k"):
        if c in df.columns:
            prop_col = c
            break

    out: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    for _, row in df.iterrows():
        raw_name = row.get(name_col)
        if raw_name is None:
            continue
        # pandas may yield float NaN for empty cells even with dtype=str
        try:
            if isinstance(raw_name, float):
                continue
        except TypeError:
            pass
        raw_str = str(raw_name).strip()
        if not raw_str or raw_str.lower() == "nan" or raw_str.upper() == "ALL OTHER NAMES":
            continue
        n = normalize_name(raw_str)
        if not n:
            continue
        try:
            rank = int(str(row[rank_col]).strip())
        except (ValueError, TypeError):
            rank = None
        try:
            count = int(str(row[count_col]).replace(",", "").strip())
        except (ValueError, TypeError):
            # Some counts are suppressed ("(S)"); skip
            continue
        prop = None
        if prop_col is not None:
            try:
                prop = float(str(row[prop_col]).strip())
            except (ValueError, TypeError):
                prop = None
        record = {
            "name_normalized": n,
            "total_count": count,
            "rank": rank,
            "proportion_per_100k": prop,
            "risk_level": classify_last_name_risk(rank),
        }
        # Deduplicate: keep the row with the highest count for each normalized name
        prev = seen.get(n)
        if prev is None or record["total_count"] > prev["total_count"]:
            seen[n] = record
    out = list(seen.values())
    logger.info("Census aggregated %d last-name rows", len(out))
    return out


# -------- Mongo import --------
async def import_all(db) -> dict[str, Any]:
    """Run full import into MongoDB. Returns a summary dict."""
    now_iso = datetime.now(timezone.utc).isoformat()

    # First names
    fn_rows = fetch_ssa_first_names()
    for r in fn_rows:
        r["created_at"] = now_iso
        r["updated_at"] = now_iso

    await db.first_name_stats.drop()
    if fn_rows:
        # Insert in chunks for speed
        chunk = 5000
        for i in range(0, len(fn_rows), chunk):
            await db.first_name_stats.insert_many(fn_rows[i : i + chunk])
    await db.first_name_stats.create_index(
        [("name_normalized", 1), ("gender", 1)], unique=True
    )
    await db.first_name_stats.create_index("name_normalized")

    # Last names
    ln_rows = fetch_census_last_names()
    for r in ln_rows:
        r["created_at"] = now_iso
        r["updated_at"] = now_iso

    await db.last_name_stats.drop()
    if ln_rows:
        chunk = 5000
        for i in range(0, len(ln_rows), chunk):
            await db.last_name_stats.insert_many(ln_rows[i : i + chunk])
    await db.last_name_stats.create_index("name_normalized", unique=True)

    # Metadata
    meta = {
        "_kind": "name_collision_import",
        "imported_at": now_iso,
        "first_name_rows": len(fn_rows),
        "last_name_rows": len(ln_rows),
        "ssa_year_min": SSA_YEAR_MIN,
        "ssa_year_max": SSA_YEAR_MAX,
        "sources": [
            "SSA Baby Names (hackerb9/ssa-baby-names mirror)",
            "U.S. Census 2010 Surnames",
        ],
    }
    await db.name_collision_meta.replace_one(
        {"_kind": "name_collision_import"}, meta, upsert=True
    )

    return {
        "first_name_rows": len(fn_rows),
        "last_name_rows": len(ln_rows),
        "imported_at": now_iso,
        "ssa_year_min": SSA_YEAR_MIN,
        "ssa_year_max": SSA_YEAR_MAX,
    }
