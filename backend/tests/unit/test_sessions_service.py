import uuid

import pytest

from app.agent import AgentReply
from app.errors import ApiError
from app.services import sessions as svc


def test_make_title_collapses_whitespace():
    assert svc.make_title("  What is\n AAPL   doing? ") == "What is AAPL doing?"


def test_make_title_trims_long_questions_to_80_chars():
    title = svc.make_title("x" * 200)
    assert len(title) == 80
    assert title.endswith("…")


def test_parse_session_id_rejects_garbage_as_not_found():
    with pytest.raises(ApiError) as exc:
        svc.parse_session_id("not-a-uuid")
    assert exc.value.status_code == 404


def test_get_session_missing_raises_not_found(db):
    with pytest.raises(ApiError) as exc:
        svc.get_session(db, uuid.uuid4())
    assert exc.value.status_code == 404


def test_record_turn_saves_both_messages_and_sets_title(db):
    created = svc.create_session(db, None)
    chat = svc.get_session(db, created.id)
    reply = AgentReply("AAPL is $1", [{"name": "GLOBAL_QUOTE", "arguments": {"symbol": "AAPL"}}])

    turn = svc.record_turn(db, chat, "What is AAPL?", reply)

    assert turn.user_message.role == "user"
    assert turn.assistant_message.tool_calls[0].name == "GLOBAL_QUOTE"
    assert turn.assistant_message.created_at > turn.user_message.created_at
    assert chat.title == "What is AAPL?"
    assert chat.updated_at == turn.assistant_message.created_at


def test_record_turn_keeps_existing_title(db):
    created = svc.create_session(db, "My research")
    chat = svc.get_session(db, created.id)
    svc.record_turn(db, chat, "What is AAPL?", AgentReply("ok"))
    assert chat.title == "My research"


def test_history_is_chronological(db):
    chat = svc.get_session(db, svc.create_session(db, None).id)
    svc.record_turn(db, chat, "q1", AgentReply("a1"))
    svc.record_turn(db, chat, "q2", AgentReply("a2"))
    assert [(h.role, h.content) for h in svc.history(chat)] == [
        ("user", "q1"),
        ("assistant", "a1"),
        ("user", "q2"),
        ("assistant", "a2"),
    ]


def test_list_sessions_counts_messages_and_sorts_newest_first(db):
    older = svc.create_session(db, "older")
    newer = svc.create_session(db, "newer")
    svc.record_turn(db, svc.get_session(db, older.id), "q", AgentReply("a"))

    listed = svc.list_sessions(db)

    assert [s.id for s in listed] == [older.id, newer.id]  # older was just updated
    assert [s.message_count for s in listed] == [2, 0]


def test_delete_session_removes_messages(db):
    from app import models

    chat = svc.get_session(db, svc.create_session(db, None).id)
    svc.record_turn(db, chat, "q", AgentReply("a"))
    svc.delete_session(db, chat.id)
    assert db.query(models.Message).count() == 0
