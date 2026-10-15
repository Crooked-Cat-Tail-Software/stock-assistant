import anyio.from_thread
from fastapi import APIRouter, Depends, Response, status

from app import schemas
from app.agent import AgentError
from app.deps import AgentDep, DbSession, enforce_rate_limit
from app.errors import ApiError
from app.services import sessions as svc

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[schemas.SessionSummary], operation_id="listSessions")
def list_sessions(db: DbSession):
    return svc.list_sessions(db)


@router.post(
    "",
    response_model=schemas.SessionSummary,
    status_code=status.HTTP_201_CREATED,
    operation_id="createSession",
)
def create_session(db: DbSession, body: schemas.SessionCreate | None = None):
    return svc.create_session(db, body.title if body else None)


@router.get("/{session_id}", response_model=schemas.SessionDetail, operation_id="getSession")
def get_session(session_id: str, db: DbSession):
    return svc.session_detail(svc.get_session(db, svc.parse_session_id(session_id)))


@router.delete(
    "/{session_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="deleteSession"
)
def delete_session(session_id: str, db: DbSession):
    svc.delete_session(db, svc.parse_session_id(session_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{session_id}/messages",
    response_model=schemas.ChatTurn,
    operation_id="sendMessage",
    dependencies=[Depends(enforce_rate_limit)],
)
def send_message(session_id: str, body: schemas.MessageCreate, db: DbSession, agent: AgentDep):
    chat = svc.get_session(db, svc.parse_session_id(session_id))

    # This route runs in a worker thread (database calls are synchronous).
    # The agent is async and shares one MCP connection that lives on the
    # main event loop, so run it there.
    try:
        reply = anyio.from_thread.run(agent.reply, svc.history(chat), body.content)
    except AgentError as exc:
        raise ApiError(502, "upstream_error", str(exc)) from exc

    return svc.record_turn(db, chat, body.content, reply)
