# Name Collision / Name Rarity Scoring Tool — PRD

## Problem statement
Estimate how many people in the United States likely share a customer's first + last name, so the identity-matching system can avoid false positives when linking customers to social profiles.

Core formula:
```
estimated_us_matches = (first_name_population * last_name_population) / 330,000,000
```

## Architecture
- **Backend**: FastAPI + Motor (MongoDB async driver).
  - Module: `backend/name_collision/`
    - `data_importer.py` — downloads SSA baby-name data (birth years 1941–2010, covering ages 16–85 in 2026) and U.S. Census 2010 surnames, normalizes, populates MongoDB.
    - `service.py` — in-memory `NameCache` (loaded at startup); `estimate_name_collision(...)`.
    - `nickname_map.py` — ~130 nickname → canonical entries.
    - `router.py` — endpoints under `/api/name-collision/*`.
  - MongoDB collections:
    - `first_name_stats` — unique index `(name_normalized, gender)`, index on `name_normalized`.
    - `last_name_stats` — unique index on `name_normalized`.
    - `name_collision_meta` — import metadata (timestamps, counts, year range).
- **Frontend**: React + shadcn/ui (Swiss/high-contrast design). `/admin/name-collision` page.

## Data sources
- SSA baby names — mirror: `https://raw.githubusercontent.com/hackerb9/ssa-baby-names/main/alldata.txt` (SSA blocks direct downloads from this IP range).
- U.S. Census 2010 surnames — `https://www2.census.gov/topics/genealogy/2010surnames/names.zip` (direct).

## API endpoints
- `POST /api/name-collision/estimate`
- `POST /api/name-collision/batch`
- `GET  /api/name-collision/stats`
- `POST /api/name-collision/import` (background)
- `POST /api/name-collision/import/sync` (sync, for tests/admin)

## User personas
- **Identity-matching engineer** calling the API from the matcher.
- **Trust & Safety / ops** using the admin page to spot-check rare vs common names.

## Core requirements (static)
1. Do not scrape live. Do not read CSVs during user requests.
2. Aggregate SSA counts across years, separate by gender.
3. Risk levels for first name (rank ≤20 high / 21–120 medium / else low), last name (rank ≤20 high / 21–500 medium / else low), and full-name collision (≥1000 high / ≥100 medium / else low).
4. Confidence penalty: high 0.45 / medium 0.25 / low 0.05.
5. Nickname canonicalization with alternate estimate.
6. Handle hyphenated last names, apostrophes, caps, initials, missing, and unknown inputs gracefully (return `risk_level="unknown"`, never zero).
7. Include caveat text about independence assumption.

## What's been implemented (2026-04-25)
- [x] MongoDB collections + indexes, in-memory cache loaded at startup.
- [x] Data importer for SSA (years 1941–2010) + Census 2010.
- [x] `estimate_name_collision` with gender auto-detect + confidence, nickname map + alternate estimate, hyphenated split, initial detection, unknown/missing handling.
- [x] Single + batch endpoints, stats endpoint, async + sync import endpoints.
- [x] Auto-seed on first startup if DB empty.
- [x] Admin page `/admin/name-collision`: dataset status bar, form, results (metrics, risk badges, nickname panel, warnings panel, hyphenated breakdown), Import/Refresh button.
- [x] Full test pass — backend 100%, frontend 100% (testing_agent_v3 iteration_1).

## Observed dataset size
- First names: 83,564 unique (92,353 name+gender combinations).
- Last names: 162,251.

## Prioritized backlog (P0/P1/P2)
- P1: expose a configurable SSA year window via env (e.g., rolling 70-year window).
- P1: gzip or msgpack cache snapshot on disk to skip Mongo load at startup.
- P2: per-state surname data (Census 2010 provides national only; state-level requires ACS).
- P2: CSV export of per-customer batch results.
- P2: Redis cache for cross-worker deployments.
- P2: admin auth (currently open per spec).
