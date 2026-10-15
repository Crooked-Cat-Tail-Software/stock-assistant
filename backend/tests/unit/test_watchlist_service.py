import pytest
from pydantic import ValidationError

from app.errors import ApiError
from app.schemas import WatchlistItemCreate
from app.services import watchlist as svc


def test_add_uppercases_symbol(db):
    item = svc.add_item(db, WatchlistItemCreate(symbol="brk.b", note="Berkshire"))
    assert item.symbol == "BRK.B"


def test_add_duplicate_is_conflict_regardless_of_case(db):
    svc.add_item(db, WatchlistItemCreate(symbol="AAPL"))
    with pytest.raises(ApiError) as exc:
        svc.add_item(db, WatchlistItemCreate(symbol="aapl"))
    assert exc.value.status_code == 409
    assert exc.value.code == "duplicate_symbol"


def test_list_is_alphabetical(db):
    for symbol in ("MSFT", "AAPL", "NVDA"):
        svc.add_item(db, WatchlistItemCreate(symbol=symbol))
    assert [i.symbol for i in svc.list_items(db)] == ["AAPL", "MSFT", "NVDA"]


def test_remove_missing_is_not_found(db):
    with pytest.raises(ApiError) as exc:
        svc.remove_item(db, "AAPL")
    assert exc.value.status_code == 404


@pytest.mark.parametrize("symbol", ["", "TOOLONGSYMBOL", "AA PL", "AAPL.", "123", "A.BCD"])
def test_invalid_symbols_are_rejected(symbol):
    with pytest.raises(ValidationError):
        WatchlistItemCreate(symbol=symbol)


def test_concurrent_duplicate_insert_is_conflict_not_crash(db, monkeypatch):
    # Simulate another request inserting AAPL between our check and our commit.
    svc.add_item(db, WatchlistItemCreate(symbol="AAPL"))
    db.expunge_all()
    monkeypatch.setattr(db, "get", lambda *args, **kwargs: None)

    with pytest.raises(ApiError) as exc:
        svc.add_item(db, WatchlistItemCreate(symbol="AAPL"))

    assert exc.value.status_code == 409
