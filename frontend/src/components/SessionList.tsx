import type { SessionSummary } from "../api/client";

interface Props {
  sessions: SessionSummary[];
  activeId: string | null;
  loading: boolean;
  error: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function SessionList({ sessions, activeId, loading, error, onSelect, onDelete }: Props) {
  return (
    <nav className="panel" aria-labelledby="sessions-heading">
      <h2 id="sessions-heading" className="panel__title">
        Conversations
      </h2>
      {error && (
        <p className="banner banner--error" role="alert">
          {error}
        </p>
      )}
      {loading && <p className="muted">Loading…</p>}
      {!loading && sessions.length === 0 && <p className="muted">No conversations yet.</p>}
      <ul className="list">
        {sessions.map((s) => (
          <li key={s.id} className={s.id === activeId ? "list__item list__item--active" : "list__item"}>
            <button
              type="button"
              className="list__main"
              aria-current={s.id === activeId ? "page" : undefined}
              onClick={() => onSelect(s.id)}
            >
              <span className="list__title">{s.title ?? "Untitled"}</span>
              <span className="list__meta">
                {s.message_count} messages · {new Date(s.updated_at).toLocaleDateString()}
              </span>
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Delete conversation “${s.title ?? "Untitled"}”`}
              onClick={() => onDelete(s.id)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
