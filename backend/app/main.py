"""Atajo - URL shortener with click analytics.

FastAPI + Azure Cosmos DB for MongoDB (PyMongo async).
"""
import logging
from contextlib import asynccontextmanager

import certifi
from fastapi import Depends, FastAPI
from pymongo import AsyncMongoClient

from .config import settings
from .dependencies import get_db
from .routers import links, redirect

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("atajo")


# APP SETUP
@asynccontextmanager
async def lifespan(app: FastAPI):
    # certifi's CA bundle, so TLS works even when the Python install has none.
    client = AsyncMongoClient(
        settings.mongo_url, tz_aware=True, tlsCAFile=certifi.where()
    )
    db = client[settings.mongo_db]

    # The unique index is what guarantees one document per short code.
    await db.links.create_index("code", unique=True)
    await db.clicks.create_index([("code", 1), ("ts", -1)])
    # Old click events are deleted automatically.
    await db.clicks.create_index(
        "ts", expireAfterSeconds=settings.clicks_retention_days * 86400
    )

    app.state.mongo, app.state.db = client, db
    log.info("Atajo started")
    try:
        yield
    finally:
        await client.close()


app = FastAPI(title="Atajo", version="1.0.0", lifespan=lifespan)


@app.get("/health", tags=["ops"])
async def health(db=Depends(get_db)):
    await db.command("ping")
    return {"status": "ok"}


app.include_router(links.router)
# The catch-all redirect must stay LAST.
app.include_router(redirect.router)
