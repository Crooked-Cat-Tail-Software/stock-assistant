from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import __version__, schemas
from app.deps import DbSession

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=schemas.Health, operation_id="getHealth")
def get_health(db: DbSession):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        body = schemas.Health(status="degraded", database="unavailable", version=__version__)
        return JSONResponse(body.model_dump(), status_code=503)
    return schemas.Health(status="ok", database="ok", version=__version__)
