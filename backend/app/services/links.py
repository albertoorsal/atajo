import logging
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from ..models.link import Link
from ..utils import generate_code
from .validate_urls import validate_target_url

log = logging.getLogger("atajo.links")


class AliasTakenError(Exception):
    pass


class CodeGenerationError(Exception):
    pass


async def create_short_link(
    db,
    long_url: str,
    alias: str | None = None,
    expires_at: datetime | None = None,
    max_attempts: int = 5,
) -> Link:
    target = validate_target_url(long_url)

    for _ in range(max_attempts):
        link = Link(code=alias or generate_code(), target_url=target, expires_at=expires_at)
        try:
            await db.links.insert_one(link.model_dump())
            return link
        except DuplicateKeyError:
            if alias:
                raise AliasTakenError(alias)
            # random code collided: loop and try another one

    raise CodeGenerationError("Could not generate a unique code")


async def resolve_target(db, code: str) -> str | None:
    """Return the destination URL for a code, or None if missing/inactive/expired."""
    doc = await db.links.find_one({"code": code, "is_active": True})
    if not doc:
        return None

    expires_at = doc.get("expires_at")
    if expires_at and expires_at <= datetime.now(timezone.utc):
        return None

    return doc["target_url"]


async def register_click(
    db, code: str, user_agent: str | None, referer: str | None
) -> None:
    try:
        await db.clicks.insert_one(
            {
                "code": code,
                "ts": datetime.now(timezone.utc),
                "user_agent": (user_agent or "")[:512] or None,
                "referer": (referer or "")[:512] or None,
            }
        )
        await db.links.update_one({"code": code}, {"$inc": {"clicks": 1}})
    except Exception:
        log.error("Failed to register click for %s", code, exc_info=True)


async def deactivate(db, code: str) -> bool:
    result = await db.links.update_one(
        {"code": code, "is_active": True}, {"$set": {"is_active": False}}
    )
    return result.matched_count > 0


async def get_stats(db, code: str) -> dict | None:
    link = await db.links.find_one({"code": code})
    if not link:
        return None

    per_day_cursor = await db.clicks.aggregate(
        [
            {"$match": {"code": code}},
            {
                "$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$ts"}},
                    "clicks": {"$sum": 1},
                }
            },
            {"$sort": {"_id": 1}},
        ]
    )
    per_day = await per_day_cursor.to_list()

    referrers_cursor = await db.clicks.aggregate(
        [
            {"$match": {"code": code}},
            {
                "$group": {
                    "_id": {"$ifNull": ["$referer", "direct"]},
                    "clicks": {"$sum": 1},
                }
            },
            {"$sort": {"clicks": -1}},
            {"$limit": 10},
        ]
    )
    referrers = await referrers_cursor.to_list()

    return {
        "code": code,
        "target_url": link["target_url"],
        "is_active": link["is_active"],
        "total_clicks": link.get("clicks", 0),
        "clicks_per_day": [{"day": d["_id"], "clicks": d["clicks"]} for d in per_day],
        "top_referrers": [{"referrer": r["_id"], "clicks": r["clicks"]} for r in referrers],
    }
