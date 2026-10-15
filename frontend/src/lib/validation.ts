// These mirror openapi.yaml so the UI can explain problems before calling the
// backend. The backend still validates everything; this only gives faster feedback.
// validation.test.ts checks that they stay in sync with the contract.

export const MAX_QUESTION_LENGTH = 2000;
export const SYMBOL_PATTERN = /^[A-Za-z]{1,10}(\.[A-Za-z]{1,2})?$/;
export const MAX_NOTE_LENGTH = 200;

export function symbolError(symbol: string): string | null {
  const value = symbol.trim();
  if (!value) return "Enter a ticker symbol.";
  if (!SYMBOL_PATTERN.test(value)) return "Use 1–10 letters, optionally with a class like BRK.B.";
  return null;
}

export function questionError(question: string): string | null {
  if (!question.trim()) return "Type a question first.";
  if (question.length > MAX_QUESTION_LENGTH)
    return `Questions are limited to ${MAX_QUESTION_LENGTH} characters.`;
  return null;
}

export function watchlistPrompt(symbol: string): string {
  return `Give me a quick overview of ${symbol}: latest price, how it has moved over the past month, and any notable news.`;
}
