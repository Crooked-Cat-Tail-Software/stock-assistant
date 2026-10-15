"""Check real HTTP responses against the response schemas in openapi.yaml."""

from functools import cache
from pathlib import Path

import yaml
from httpx import Response
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SPEC_PATH = Path(__file__).resolve().parents[3] / "openapi.yaml"
SPEC_URI = "urn:openapi"


@cache
def spec() -> dict:
    return yaml.safe_load(SPEC_PATH.read_text())


@cache
def _registry() -> Registry:
    return Registry().with_resource(
        SPEC_URI, Resource.from_contents(spec(), default_specification=DRAFT202012)
    )


def _escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def assert_conforms(response: Response, path: str, method: str) -> None:
    """Assert the response's status is documented and its JSON body matches the schema.

    `path` is the OpenAPI path template, e.g. "/api/sessions/{sessionId}".
    """
    operation = spec()["paths"][path][method.lower()]
    status = str(response.status_code)
    assert status in operation["responses"], (
        f"{method.upper()} {path} returned {status}, which openapi.yaml does not document"
    )

    response_pointer = "/".join(["#", "paths", _escape(path), method.lower(), "responses", status])
    documented = operation["responses"][status]
    if "$ref" in documented:  # shared response, e.g. #/components/responses/NotFound
        response_pointer = documented["$ref"]
        name = response_pointer.rsplit("/", 1)[-1]
        documented = spec()["components"]["responses"][name]

    if "content" not in documented:
        assert not response.content, f"{status} should have no body"
        return

    schema_pointer = f"{response_pointer}/content/application~1json/schema"
    validator = Draft202012Validator(
        {"$ref": SPEC_URI + schema_pointer},
        registry=_registry(),
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(response.json()), key=lambda e: list(e.path))
    assert not errors, "Response does not match openapi.yaml:\n" + "\n".join(
        f"  at {list(e.path)}: {e.message}" for e in errors
    )
