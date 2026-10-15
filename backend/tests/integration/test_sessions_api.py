"""Key chat workflows, end to end over HTTP."""

import uuid

from app.agent import AgentReply
from app.agent.fake import FAIL_TRIGGER
from tests.integration.contract import assert_conforms

SESSIONS = "/api/sessions"
SESSION = "/api/sessions/{sessionId}"
MESSAGES = "/api/sessions/{sessionId}/messages"


def new_session(client) -> str:
    response = client.post(SESSIONS)
    assert response.status_code == 201
    assert_conforms(response, SESSIONS, "post")
    return response.json()["id"]


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert_conforms(response, "/api/health", "get")
    assert response.json()["database"] == "ok"


def test_ask_a_question_and_read_it_back(client):
    session_id = new_session(client)

    response = client.post(
        f"{SESSIONS}/{session_id}/messages", json={"content": "What is AAPL's latest price?"}
    )

    assert response.status_code == 200
    assert_conforms(response, MESSAGES, "post")
    turn = response.json()
    assert turn["user_message"]["content"] == "What is AAPL's latest price?"
    assert turn["assistant_message"]["tool_calls"][0]["name"] == "GLOBAL_QUOTE"

    detail = client.get(f"{SESSIONS}/{session_id}")
    assert_conforms(detail, SESSION, "get")
    body = detail.json()
    assert body["title"] == "What is AAPL's latest price?"
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]


def test_agent_receives_earlier_turns_as_history(client):
    session_id = new_session(client)
    client.post(f"{SESSIONS}/{session_id}/messages", json={"content": "hello"})

    second = client.post(f"{SESSIONS}/{session_id}/messages", json={"content": "and now?"})

    assert "2 earlier messages" in second.json()["assistant_message"]["content"]


def test_sessions_are_listed_newest_first_with_counts(client):
    first = new_session(client)
    second = new_session(client)
    client.post(f"{SESSIONS}/{first}/messages", json={"content": "bump"})

    response = client.get(SESSIONS)

    assert_conforms(response, SESSIONS, "get")
    listed = response.json()
    assert [s["id"] for s in listed] == [first, second]
    assert [s["message_count"] for s in listed] == [2, 0]


def test_sessions_survive_an_app_restart(make_client):
    session_id = new_session(make_client())
    restarted = make_client()
    assert restarted.get(f"{SESSIONS}/{session_id}").status_code == 200


def test_delete_session(client):
    session_id = new_session(client)
    client.post(f"{SESSIONS}/{session_id}/messages", json={"content": "q"})

    response = client.delete(f"{SESSIONS}/{session_id}")

    assert response.status_code == 204
    assert_conforms(response, SESSION, "delete")
    missing = client.get(f"{SESSIONS}/{session_id}")
    assert missing.status_code == 404
    assert_conforms(missing, SESSION, "get")


def test_unknown_and_malformed_session_ids_are_404(client):
    for session_id in (str(uuid.uuid4()), "not-a-uuid"):
        response = client.post(f"{SESSIONS}/{session_id}/messages", json={"content": "hi"})
        assert response.status_code == 404
        assert_conforms(response, MESSAGES, "post")
        assert response.json()["code"] == "not_found"


def test_overlong_and_blank_questions_are_rejected(client):
    session_id = new_session(client)
    for content in ("x" * 2001, "   "):
        response = client.post(f"{SESSIONS}/{session_id}/messages", json={"content": content})
        assert response.status_code == 422
        assert_conforms(response, MESSAGES, "post")
        assert response.json()["code"] == "validation_error"


def test_question_of_exactly_2000_chars_is_accepted(client):
    session_id = new_session(client)
    response = client.post(f"{SESSIONS}/{session_id}/messages", json={"content": "x" * 2000})
    assert response.status_code == 200


def test_agent_failure_returns_502_and_saves_nothing(client):
    session_id = new_session(client)

    response = client.post(
        f"{SESSIONS}/{session_id}/messages", json={"content": f"AAPL {FAIL_TRIGGER}"}
    )

    assert response.status_code == 502
    assert_conforms(response, MESSAGES, "post")
    assert response.json()["code"] == "upstream_error"
    detail = client.get(f"{SESSIONS}/{session_id}").json()
    assert detail["message_count"] == 0
    assert detail["title"] is None


def test_rate_limit(make_client):
    client = make_client(rate_limit_per_minute=2)
    session_id = new_session(client)
    url = f"{SESSIONS}/{session_id}/messages"

    assert client.post(url, json={"content": "1"}).status_code == 200
    assert client.post(url, json={"content": "2"}).status_code == 200
    limited = client.post(url, json={"content": "3"})

    assert limited.status_code == 429
    assert_conforms(limited, MESSAGES, "post")
    assert int(limited.headers["Retry-After"]) > 0


class UnparseableArgumentsAgent:
    async def reply(self, history, question):
        return AgentReply("done", [{"name": "GLOBAL_QUOTE", "arguments": None}])


def test_tool_call_without_parseable_arguments_conforms(make_client):
    client = make_client(agent=UnparseableArgumentsAgent())
    session_id = new_session(client)

    response = client.post(f"{SESSIONS}/{session_id}/messages", json={"content": "q"})

    assert response.status_code == 200
    assert_conforms(response, MESSAGES, "post")
    assert response.json()["assistant_message"]["tool_calls"][0]["arguments"] is None


class BrokenSessionFactory:
    def __call__(self):
        from sqlalchemy.exc import OperationalError

        class Broken:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, *args, **kwargs):
                raise OperationalError("SELECT 1", {}, Exception("connection refused"))

        return Broken()


def test_health_reports_503_when_database_is_down(client):
    client.app.state.session_factory = BrokenSessionFactory()

    response = client.get("/api/health")

    assert response.status_code == 503
    assert_conforms(response, "/api/health", "get")
    assert response.json() == {"status": "degraded", "database": "unavailable", "version": "0.1.0"}


def test_unknown_api_route_uses_error_shape(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
