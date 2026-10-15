"""Business logic for chat sessions. No HTTP here, so it is easy to unit test."""

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.agent import AgentReply, HistoryItem
from app.errors import not_found

TITLE_MAX = 80


def make_title(question: str) -> str:
    """Use the first question, collapsed to one line and trimmed, as the session title."""
    title = " ".join(question.split())
    return title if len(title) <= TITLE_MAX else title[: TITLE_MAX - 1].rstrip() + "…"


def parse_session_id(raw: str) -> uuid.UUID:
    # A malformed ID can't match any session, so treat it as "not found" (per the contract).
    try:
        return uuid.UUID(raw)
    except ValueError:
        raise not_found("Session") from None


def _summary(chat: models.ChatSession, message_count: int) -> schemas.SessionSummary:
    return schemas.SessionSummary(
        id=chat.id,
        title=chat.title,
        message_count=message_count,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


def list_sessions(db: Session) -> list[schemas.SessionSummary]:
    counts = (
        select(models.Message.session_id, func.count().label("n"))
        .group_by(models.Message.session_id)
        .subquery()
    )
    rows = db.execute(
        select(models.ChatSession, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.session_id == models.ChatSession.id)
        .order_by(models.ChatSession.updated_at.desc())
    ).all()
    return [_summary(chat, n) for chat, n in rows]


def create_session(db: Session, title: str | None) -> schemas.SessionSummary:
    chat = models.ChatSession(title=make_title(title) if title else None)
    db.add(chat)
    db.commit()
    return _summary(chat, 0)


def get_session(db: Session, session_id: uuid.UUID) -> models.ChatSession:
    chat = db.get(models.ChatSession, session_id)
    if chat is None:
        raise not_found("Session")
    return chat


def session_detail(chat: models.ChatSession) -> schemas.SessionDetail:
    return schemas.SessionDetail(
        **_summary(chat, len(chat.messages)).model_dump(),
        messages=[schemas.Message.model_validate(m) for m in chat.messages],
    )


def delete_session(db: Session, session_id: uuid.UUID) -> None:
    db.delete(get_session(db, session_id))
    db.commit()


def history(chat: models.ChatSession) -> list[HistoryItem]:
    return [HistoryItem(role=m.role, content=m.content) for m in chat.messages]  # type: ignore[arg-type]


def record_turn(
    db: Session, chat: models.ChatSession, question: str, reply: AgentReply
) -> schemas.ChatTurn:
    """Save the question and the reply together, only after the agent succeeded."""
    now = models.utcnow()
    user_msg = models.Message(session=chat, role="user", content=question, created_at=now)
    # Give the reply a strictly later timestamp so ordering is stable even
    # when the clock resolution is coarse.
    assistant_msg = models.Message(
        session=chat,
        role="assistant",
        content=reply.content,
        tool_calls=reply.tool_calls,
        created_at=models.utcnow(),
    )
    if assistant_msg.created_at <= now:
        assistant_msg.created_at = now + timedelta(microseconds=1)

    if chat.title is None:
        chat.title = make_title(question)
    chat.updated_at = assistant_msg.created_at
    db.add_all([user_msg, assistant_msg])
    db.commit()
    return schemas.ChatTurn(
        user_message=schemas.Message.model_validate(user_msg),
        assistant_message=schemas.Message.model_validate(assistant_msg),
    )
