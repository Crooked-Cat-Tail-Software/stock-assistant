"""The app must implement exactly the operations defined in openapi.yaml.

Compares the hand-written contract with the OpenAPI document FastAPI generates
from the code, so a route that is added, removed, or renamed without updating
the contract fails this test.
"""

from tests.integration.contract import spec

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _operations(document: dict) -> dict[tuple[str, str], str]:
    return {
        (method.upper(), path): operation["operationId"]
        for path, item in document["paths"].items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    }


def test_implemented_operations_match_contract(client):
    generated = {
        (method, path.replace("{session_id}", "{sessionId}")): op_id
        for (method, path), op_id in _operations(client.app.openapi()).items()
    }
    assert generated == _operations(spec())
