import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

os.environ.setdefault("MONGO_URL", "mongodb://unused")
os.environ["API_KEYS"] = "test-key"

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.main import app
from app.services import validate_target_url

settings.api_keys = "test-key"
AUTH = {"X-API-Key": "test-key"}


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self):
        return self.docs


class FakeCollection:
    def __init__(self, unique_field=None):
        self.docs = []
        self.unique_field = unique_field

    def _match(self, doc, query):
        return all(doc.get(k) == v for k, v in query.items())

    async def insert_one(self, doc):
        f = self.unique_field
        if f and any(d[f] == doc[f] for d in self.docs):
            raise DuplicateKeyError("dup")
        self.docs.append(dict(doc))

    async def find_one(self, query):
        return next((d for d in self.docs if self._match(d, query)), None)

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        if doc:
            for k, v in update.get("$set", {}).items():
                doc[k] = v
            for k, v in update.get("$inc", {}).items():
                doc[k] = doc.get(k, 0) + v
        return SimpleNamespace(matched_count=1 if doc else 0)

    async def aggregate(self, pipeline):
        code = pipeline[0]["$match"]["code"]
        rows = [d for d in self.docs if d["code"] == code]
        group_id = pipeline[1]["$group"]["_id"]
        counts: dict[str, int] = {}
        for d in rows:
            key = d["ts"].strftime("%Y-%m-%d") if "$dateToString" in group_id else (d["referer"] or "direct")
            counts[key] = counts.get(key, 0) + 1
        return FakeCursor([{"_id": k, "clicks": v} for k, v in counts.items()])


@pytest.fixture
def client():
    db = SimpleNamespace(links=FakeCollection("code"), clicks=FakeCollection())
    app.state.db = db
    # No `with`: the lifespan (real Mongo connection) is not started.
    yield TestClient(app, follow_redirects=False), db


def test_validate_target_url():
    assert validate_target_url(" https://example.com/a ") == "https://example.com/a"
    for bad in ["ftp://x.com", "http://localhost", "http://10.0.0.1", "http://[::1]/", "http://a.internal"]:
        with pytest.raises(ValueError):
            validate_target_url(bad)


def test_requires_api_key(client):
    c, _ = client
    assert c.post("/links", json={"url": "https://example.com"}).status_code == 401
    assert c.post("/links", json={"url": "https://example.com"}, headers={"X-API-Key": "nope"}).status_code == 401


def test_create_redirect_and_stats(client):
    c, db = client
    res = c.post("/links", json={"url": "https://example.com"}, headers=AUTH)
    assert res.status_code == 201
    code = res.json()["code"]
    assert res.json()["short_url"].endswith(f"/{code}")

    r = c.get(f"/{code}", headers={"referer": "https://news.site"})
    assert r.status_code == 307
    assert r.headers["location"] == "https://example.com/"

    stats = c.get(f"/links/{code}/stats", headers=AUTH).json()
    assert stats["total_clicks"] == 1
    assert stats["top_referrers"] == [{"referrer": "https://news.site", "clicks": 1}]


def test_alias_conflict_and_reserved(client):
    c, _ = client
    assert c.post("/links", json={"url": "https://a.com", "alias": "promo"}, headers=AUTH).status_code == 201
    assert c.post("/links", json={"url": "https://b.com", "alias": "promo"}, headers=AUTH).status_code == 409
    assert c.post("/links", json={"url": "https://b.com", "alias": "health"}, headers=AUTH).status_code == 422


def test_blocked_destination(client):
    c, _ = client
    assert c.post("/links", json={"url": "http://127.0.0.1/admin"}, headers=AUTH).status_code == 422


def test_deactivate(client):
    c, _ = client
    c.post("/links", json={"url": "https://a.com", "alias": "gone"}, headers=AUTH)
    assert c.delete("/links/gone", headers=AUTH).status_code == 204
    assert c.get("/gone").status_code == 404
    assert c.delete("/links/gone", headers=AUTH).status_code == 404


def test_expired_link_404(client):
    c, db = client
    db.links.docs.append({
        "code": "old", "target_url": "https://a.com", "is_active": True,
        "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1), "clicks": 0,
    })
    assert c.get("/old").status_code == 404


def test_junk_paths_404(client):
    c, _ = client
    assert c.get("/favicon.ico").status_code == 404
    assert c.get("/x").status_code == 404
