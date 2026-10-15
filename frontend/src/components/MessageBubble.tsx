import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../api/client";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <article className={`message message--${message.role}`} aria-label={isUser ? "You" : "Assistant"}>
      {isUser ? (
        <p className="message__text">{message.content}</p>
      ) : (
        // react-markdown does not render raw HTML, so agent output can't inject markup.
        <div className="message__markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
      )}
      {message.tool_calls.length > 0 && (
        <ul className="tools" aria-label="Data sources used">
          {message.tool_calls.map((call, i) => (
            <li key={i} className="tools__chip" title={formatArgs(call.arguments)}>
              {call.name}
              {typeof call.arguments?.symbol === "string" && ` · ${call.arguments.symbol}`}
            </li>
          ))}
        </ul>
      )}
    </article>
  );
}

function formatArgs(args: Record<string, unknown> | null | undefined): string {
  if (!args) return "";
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(", ");
}
