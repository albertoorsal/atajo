from datetime import datetime, timezone
from pydantic import BaseModel, Field, HttpUrl, field_validator

from ..utils import CODE_RE, RESERVED_CODES


# Document stored in the `links` collection.
class Link(BaseModel):
    code : str
    target_url : str
    is_active: bool = True
    expires_at : datetime | None = None
    created_at : datetime = Field(default_factory=lambda : datetime.now(timezone.utc))
    clicks: int = 0


# Request / response schemas
class LinkCreate(BaseModel):
    url : HttpUrl
    alias : str | None = None
    expires_at : datetime | None = None

    @field_validator("alias")
    @classmethod
    def check_alias(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not CODE_RE.fullmatch(v):
            raise ValueError("Alias must be 3-32 chars: letters, digits, '-' or '_'")
        if v.lower() in RESERVED_CODES:
            raise ValueError("Alias is reserved")
        return v

    @field_validator("expires_at")
    @classmethod
    def check_expiry(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("expires_at must be in the future")
        return v


class LinkOut(BaseModel):
    code : str
    short_url : str
    target_url : str
    expires_at : datetime | None = None


class DayCount(BaseModel):
    day : str
    clicks : int


class ReferrerCount(BaseModel):
    referrer : str
    clicks : int


class StatsOut(BaseModel):
    code : str
    target_url : str
    is_active : bool
    total_clicks : int
    clicks_per_day : list[DayCount]
    top_referrers : list[ReferrerCount]
