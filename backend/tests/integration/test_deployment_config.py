"""Behavior that only applies in deployed configurations."""

from tests.integration.contract import assert_conforms

TOKEN = "test-internal-token"  # noqa: S105 (dummy value)


def test_api_requires_internal_token_when_configured(make_client):
    client = make_client(internal_api_token=TOKEN)

    missing = client.get("/api/sessions")
    wrong = client.get("/api/sessions", headers={"X-Internal-Token": "nope"})
    right = client.get("/api/sessions", headers={"X-Internal-Token": TOKEN})

    assert missing.status_code == 403
    assert missing.json()["code"] == "forbidden"
    assert wrong.status_code == 403
    assert right.status_code == 200


def test_health_stays_open_and_reports_commit(make_client):
    client = make_client(internal_api_token=TOKEN, git_commit="abc1234")

    response = client.get("/api/health")

    assert response.status_code == 200
    assert_conforms(response, "/api/health", "get")
    assert response.json()["commit"] == "abc1234"


def test_no_token_configured_means_no_check(client):
    assert client.get("/api/sessions").status_code == 200
    assert client.get("/api/health").json()["commit"] is None


def test_empty_token_setting_disables_the_check(make_client):
    client = make_client(internal_api_token="")
    assert client.get("/api/sessions").status_code == 200
