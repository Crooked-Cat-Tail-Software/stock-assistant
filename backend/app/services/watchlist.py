"""Business logic for the watchlist."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, schemas
from app.errors import ApiError, not_found


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def list_items(db: Session) -> list[models.WatchlistItem]:
    return list(db.scalars(select(models.WatchlistItem).order_by(models.WatchlistItem.symbol)))


def add_item(db: Session, data: schemas.WatchlistItemCreate) -> models.WatchlistItem:
    symbol = normalize_symbol(data.symbol)
    duplicate = ApiError(409, "duplicate_symbol", f"{symbol} is already on the watchlist")
    if db.get(models.WatchlistItem, symbol) is not None:
        raise duplicate
    item = models.WatchlistItem(symbol=symbol, note=data.note or None)
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        # Another request added the same symbol between our check and commit.
        db.rollback()
        raise duplicate from None
    return item


def remove_item(db: Session, symbol: str) -> None:
    item = db.get(models.WatchlistItem, normalize_symbol(symbol))
    if item is None:
        raise not_found("Watchlist symbol")
    db.delete(item)
    db.commit()
