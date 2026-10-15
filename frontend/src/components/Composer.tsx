import { useState, type FormEvent, type KeyboardEvent } from "react";
import { MAX_QUESTION_LENGTH, questionError } from "../lib/validation";

interface Props {
  initialText?: string;
  disabled: boolean;
  onSend: (text: string) => Promise<boolean>;
}

export function Composer({ initialText = "", disabled, onSend }: Props) {
  const [text, setText] = useState(initialText);
  const [hint, setHint] = useState<string | null>(null);
  const over = text.length > MAX_QUESTION_LENGTH;

  async function submit(event?: FormEvent) {
    event?.preventDefault();
    if (disabled) return;
    const problem = questionError(text);
    setHint(problem);
    if (problem) return;
    if (await onSend(text.trim())) setText("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends; Shift+Enter adds a new line.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void submit();
    }
  }

  return (
    <form className="composer" onSubmit={submit}>
      <label htmlFor="question" className="visually-hidden">
        Your question
      </label>
      <textarea
        id="question"
        value={text}
        onChange={(e) => {
          setText(e.target.value);
          setHint(null);
        }}
        onKeyDown={onKeyDown}
        placeholder="Ask about a stock, e.g. “How has NVDA moved this week compared with AMD?”"
        rows={2}
        autoFocus
        aria-invalid={over || undefined}
        aria-describedby="question-meta"
      />
      <div className="composer__bar">
        <span id="question-meta" className={over ? "composer__count composer__count--over" : "composer__count"}>
          {hint ?? `${text.length} / ${MAX_QUESTION_LENGTH}`}
        </span>
        <button type="submit" disabled={disabled || over}>
          {disabled ? "Researching…" : "Ask"}
        </button>
      </div>
    </form>
  );
}
