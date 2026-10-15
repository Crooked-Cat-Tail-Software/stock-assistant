from fastapi import APIRouter, Response, status

from app import schemas
from app.deps import DbSession
from app.services import watchlist as svc

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[schemas.WatchlistItem], operation_id="listWatchlist")
def list_watchlist(db: DbSession):
    return svc.list_items(db)


@router.post(
    "",
    response_model=schemas.WatchlistItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="addWatchlistItem",
)
def add_watchlist_item(body: schemas.WatchlistItemCreate, db: DbSession):
    return svc.add_item(db, body)


@router.delete(
    "/{symbol}", status_code=status.HTTP_204_NO_CONTENT, operation_id="removeWatchlistItem"
)
def remove_watchlist_item(symbol: str, db: DbSession):
    svc.remove_item(db, symbol)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
