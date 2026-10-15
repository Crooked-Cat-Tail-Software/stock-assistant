from tests.integration.contract import assert_conforms

WATCHLIST = "/api/watchlist"
ITEM = "/api/watchlist/{symbol}"


def test_add_list_and_remove(client):
    added = client.post(WATCHLIST, json={"symbol": "aapl", "note": "core holding"})
    assert added.status_code == 201
    assert_conforms(added, WATCHLIST, "post")
    assert added.json()["symbol"] == "AAPL"

    client.post(WATCHLIST, json={"symbol": "BRK.B"})
    listed = client.get(WATCHLIST)
    assert_conforms(listed, WATCHLIST, "get")
    assert [i["symbol"] for i in listed.json()] == ["AAPL", "BRK.B"]

    removed = client.delete(f"{WATCHLIST}/aapl")
    assert removed.status_code == 204
    assert_conforms(removed, ITEM, "delete")
    assert [i["symbol"] for i in client.get(WATCHLIST).json()] == ["BRK.B"]


def test_duplicate_symbol_is_409(client):
    client.post(WATCHLIST, json={"symbol": "AAPL"})
    response = client.post(WATCHLIST, json={"symbol": "aapl"})
    assert response.status_code == 409
    assert_conforms(response, WATCHLIST, "post")
    assert response.json()["code"] == "duplicate_symbol"


def test_invalid_symbol_is_422(client):
    response = client.post(WATCHLIST, json={"symbol": "NOT A TICKER"})
    assert response.status_code == 422
    assert_conforms(response, WATCHLIST, "post")


def test_removing_unknown_symbol_is_404(client):
    response = client.delete(f"{WATCHLIST}/ZZZZ")
    assert response.status_code == 404
    assert_conforms(response, ITEM, "delete")
