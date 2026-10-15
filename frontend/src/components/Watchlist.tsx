import { useState, type FormEvent } from "react";
import { useWatchlist } from "../hooks/useWatchlist";
import { MAX_NOTE_LENGTH, symbolError } from "../lib/validation";

interface Props {
  onAsk: (symbol: string) => void;
}

export function Watchlist({ onAsk }: Props) {
  const { items, loading, error, add, remove } = useWatchlist();
  const [symbol, setSymbol] = useState("");
  const [note, setNote] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const problem = symbolError(symbol);
    if (problem) {
      setFormError(problem);
      return;
    }
    setSaving(true);
    const failure = await add(symbol, note);
    setSaving(false);
    setFormError(failure);
    if (!failure) {
      setSymbol("");
      setNote("");
    }
  }

  return (
    <section className="panel" aria-labelledby="watchlist-heading">
      <h2 id="watchlist-heading" className="panel__title">
        Watchlist
      </h2>

      <form className="watch-form" onSubmit={submit} noValidate>
        <label htmlFor="watch-symbol" className="visually-hidden">
          Ticker symbol
        </label>
        <input
          id="watch-symbol"
          value={symbol}
          onChange={(e) => {
            setSymbol(e.target.value.toUpperCase());
            setFormError(null);
          }}
          placeholder="Ticker"
          autoComplete="off"
          maxLength={13}
          aria-invalid={formError ? true : undefined}
          aria-describedby={formError ? "watch-error" : undefined}
        />
        <label htmlFor="watch-note" className="visually-hidden">
          Note (optional)
        </label>
        <input
          id="watch-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (optional)"
          maxLength={MAX_NOTE_LENGTH}
        />
        <button type="submit" disabled={saving}>
          Add
        </button>
      </form>
      {formError && (
        <p id="watch-error" className="field-error" role="alert">
          {formError}
        </p>
      )}

      {error && (
        <p className="banner banner--error" role="alert">
          {error}
        </p>
      )}
      {loading && <p className="muted">Loading…</p>}
      {!loading && items.length === 0 && <p className="muted">Add tickers you follow.</p>}

      <ul className="list">
        {items.map((item) => (
          <li key={item.symbol} className="list__item">
            <div className="list__main list__main--static">
              <span className="list__title">{item.symbol}</span>
              {item.note && <span className="list__meta">{item.note}</span>}
            </div>
            <button
              type="button"
              className="small-button"
              aria-label={`Ask about ${item.symbol}`}
              onClick={() => onAsk(item.symbol)}
            >
              Ask
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Remove ${item.symbol}`}
              onClick={() => void remove(item.symbol)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
