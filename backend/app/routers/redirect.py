from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..dependencies import get_db
from ..services import register_click, resolve_target
from ..utils import is_valid_code

# NOTE: this catch-all router must be included LAST in main.py.
router = APIRouter()


@router.get("/{code}", include_in_schema=False)
async def redirect(
    code: str,
    request: Request,
    background: BackgroundTasks,
    db=Depends(get_db),
):
    # Reject junk paths (favicon.ico, scanners, etc.) before touching the database.
    if not is_valid_code(code):
        raise HTTPException(status_code=404, detail="Link not found")

    target = await resolve_target(db, code)
    if target is None:
        raise HTTPException(status_code=404, detail="Link not found")

    background.add_task(
        register_click,
        db,
        code,
        request.headers.get("user-agent"),
        request.headers.get("referer"),
    )
    # 307 + no-store so every visit passes through the server and gets counted.
    return RedirectResponse(
        target, status_code=307, headers={"Cache-Control": "no-store"}
    )
