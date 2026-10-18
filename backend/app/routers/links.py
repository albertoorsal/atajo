from fastapi import APIRouter, Depends, HTTPException, Response

from ..config import settings
from ..dependencies import get_db, require_api_key
from ..models import LinkCreate, LinkOut, StatsOut
from ..services import (
    AliasTakenError,
    CodeGenerationError,
    create_short_link,
    deactivate,
    get_stats,
)

router = APIRouter(
    prefix="/links", tags=["links"], dependencies=[Depends(require_api_key)]
)


@router.post("", response_model=LinkOut, status_code=201)
async def create_link(payload: LinkCreate, db=Depends(get_db)):
    try:
        link = await create_short_link(
            db, str(payload.url), payload.alias, payload.expires_at
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except AliasTakenError:
        raise HTTPException(status_code=409, detail="Alias already in use")
    except CodeGenerationError:
        raise HTTPException(
            status_code=503, detail="Could not generate a unique code, try again"
        )

    return LinkOut(
        code=link.code,
        short_url=f"{settings.base_url.rstrip('/')}/{link.code}",
        target_url=link.target_url,
        expires_at=link.expires_at,
    )


@router.get("/{code}/stats", response_model=StatsOut)
async def link_stats(code: str, db=Depends(get_db)):
    stats = await get_stats(db, code)
    if stats is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return stats


@router.delete("/{code}", status_code=204)
async def deactivate_link(code: str, db=Depends(get_db)):
    if not await deactivate(db, code):
        raise HTTPException(status_code=404, detail="Link not found")

    return Response(status_code=204)
