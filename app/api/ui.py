from pathlib import Path

from fastapi import (
    APIRouter,
    Request,
)
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

APP_DIR = Path(__file__).resolve().parents[1]

templates = Jinja2Templates(
    directory=str(APP_DIR / "templates"),
)

router = APIRouter(
    tags=["UI"],
)


@router.get(
    "/ui",
    response_class=HTMLResponse,
)
async def dashboard(
    request: Request,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={},
    )
