"""
Backend tests for Name Collision / Rarity Scoring Tool.
Covers: /api/name-collision/stats, /estimate, /batch.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://collision-scorer.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api/name-collision"

CAVEAT_PREFIX = "estimated_us_matches is a statistical estimate"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- /stats ---
class TestStats:
    def test_stats_loaded(self, client):
        r = client.get(f"{API}/stats", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["loaded"] is True
        assert data["first_name_count"] > 80000, f"expected ~83K, got {data['first_name_count']}"
        assert data["last_name_count"] > 160000, f"expected ~162K, got {data['last_name_count']}"
        meta = data.get("meta") or {}
        assert "imported_at" in meta
        assert meta.get("ssa_year_min") == 1941
        assert meta.get("ssa_year_max") == 2010


# --- /estimate ---
class TestEstimate:
    def _post(self, client, payload):
        r = client.post(f"{API}/estimate", json=payload, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        return r.json()

    def test_daniel_norris_male(self, client):
        d = self._post(client, {"first_name": "Daniel", "last_name": "Norris", "gender": "M"})
        assert d["first_name_population"] > 1_000_000, d["first_name_population"]
        assert 50_000 < d["last_name_population"] < 200_000, d["last_name_population"]
        assert 400 <= d["estimated_us_matches"] <= 700, d["estimated_us_matches"]
        assert d["full_name_collision_risk"] == "medium"
        assert d["confidence_penalty"] == 0.25
        assert d["gender_used"] == "M"
        assert "SSA Baby Names" in d["data_sources"]
        assert "U.S. Census 2010 Surnames" in d["data_sources"]
        assert "(first_name_population * last_name_population)" in d["formula"]
        assert d["caveat"].startswith(CAVEAT_PREFIX)

    def test_michael_smith_autodetect(self, client):
        d = self._post(client, {"first_name": "Michael", "last_name": "Smith"})
        assert d["gender_used"] == "M"
        assert d["gender_confidence"] is not None and d["gender_confidence"] >= 0.95
        assert d["estimated_us_matches"] > 1000
        assert d["full_name_collision_risk"] == "high"
        assert d["confidence_penalty"] == 0.45

    def test_mike_tait_nickname(self, client):
        d = self._post(client, {"first_name": "Mike", "last_name": "Tait"})
        assert d["nickname_canonical"] == "michael", d["nickname_canonical"]
        alt = d.get("alternate_estimate_for_canonical")
        assert alt is not None, "alternate_estimate_for_canonical missing"
        assert alt.get("first_name_population", 0) > 0
        assert alt.get("estimated_us_matches") is not None

    def test_hyphenated_last_name(self, client):
        d = self._post(client, {"first_name": "Sarah", "last_name": "Smith-Jones"})
        parts = d.get("hyphenated_last_name_parts")
        assert parts is not None and len(parts) == 2, parts
        names = {p["part"] for p in parts}
        assert "smith" in names and "jones" in names
        for p in parts:
            assert p["population"] is not None
            assert p["rank"] is not None

    def test_initial_first_name(self, client):
        d = self._post(client, {"first_name": "J", "last_name": "Smith"})
        assert "first_name_is_initial_high_uncertainty" in d["warnings"]
        assert d["estimated_us_matches"] is None
        assert d["full_name_collision_risk"] == "unknown"

    def test_missing_last_name(self, client):
        d = self._post(client, {"first_name": "Daniel", "last_name": ""})
        assert "missing_last_name" in d["warnings"]
        assert d["estimated_us_matches"] is None

    def test_unknown_last_name(self, client):
        d = self._post(client, {"first_name": "Daniel", "last_name": "Xyzzzqqq"})
        assert d["last_name_risk_level"] == "unknown"
        assert "last_name_not_found" in d["warnings"]
        assert d["estimated_us_matches"] is None

    def test_obrien_apostrophe(self, client):
        d = self._post(client, {"first_name": "Patrick", "last_name": "O'Brien"})
        # Normalization should map to census entry; population should be populated
        assert d["last_name_population"] is not None and d["last_name_population"] > 0
        assert d["last_name_risk_level"] != "unknown"

    def test_caps_mary(self, client):
        d = self._post(client, {"first_name": "MARY", "last_name": "SMITH"})
        assert d["first_name_population"] is not None and d["first_name_population"] > 0
        assert d["last_name_population"] is not None and d["last_name_population"] > 0

    def test_caveat_always_present(self, client):
        d = self._post(client, {"first_name": "Daniel", "last_name": "Norris"})
        assert d["caveat"].startswith(CAVEAT_PREFIX)


# --- /batch ---
class TestBatch:
    def test_batch_three_customers(self, client):
        payload = {
            "customers": [
                {"id": "c1", "first_name": "Daniel", "last_name": "Norris", "gender": "M"},
                {"id": "c2", "first_name": "Mike", "last_name": "Tait"},
                {"id": "c3", "first_name": "Michael", "last_name": "Smith"},
            ]
        }
        r = client.post(f"{API}/batch", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "results" in data and len(data["results"]) == 3
        ids = [x["id"] for x in data["results"]]
        assert ids == ["c1", "c2", "c3"]
        for item in data["results"]:
            assert "estimated_us_matches" in item
            assert "full_name_collision_risk" in item
            assert "confidence_penalty" in item
            assert "nickname_canonical" in item
        # mike -> michael
        mike_row = next(x for x in data["results"] if x["id"] == "c2")
        assert mike_row["nickname_canonical"] == "michael"
