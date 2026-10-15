import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { MAX_NOTE_LENGTH, MAX_QUESTION_LENGTH, SYMBOL_PATTERN, questionError, symbolError } from "./validation";

describe("symbolError", () => {
  it.each(["AAPL", "aapl", "BRK.B", " msft "])("accepts %j", (symbol) => {
    expect(symbolError(symbol)).toBeNull();
  });

  it.each(["", "   ", "TOOLONGSYMBOL", "AA PL", "AAPL.", "123", "A.BCD"])("rejects %j", (symbol) => {
    expect(symbolError(symbol)).not.toBeNull();
  });
});

describe("questionError", () => {
  it("rejects blank questions", () => expect(questionError("  \n ")).not.toBeNull());
  it("accepts exactly the limit", () => expect(questionError("x".repeat(MAX_QUESTION_LENGTH))).toBeNull());
  it("rejects one over the limit", () => expect(questionError("x".repeat(MAX_QUESTION_LENGTH + 1))).not.toBeNull());
});

// Vitest runs from the frontend/ folder; the contract lives at the repo root.
const contract = readFileSync(resolve(process.cwd(), "../openapi.yaml"), "utf8");

describe("client-side rules match openapi.yaml", () => {
  it("uses the contract's symbol pattern", () => {
    // In YAML double-quoted strings a backslash is written twice.
    expect(contract).toContain(`pattern: "${SYMBOL_PATTERN.source.replaceAll("\\", "\\\\")}"`);
  });

  it("uses the contract's length limits", () => {
    expect(contract).toMatch(new RegExp(`MessageCreate:[\\s\\S]*?maxLength: ${MAX_QUESTION_LENGTH}\\b`));
    expect(contract).toMatch(new RegExp(`WatchlistItemCreate:[\\s\\S]*?maxLength: ${MAX_NOTE_LENGTH}\\b`));
  });
});
