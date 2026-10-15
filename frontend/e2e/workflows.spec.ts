/**
 * Key user workflows from product-spec.md, end to end:
 * browser → production frontend build → Vite proxy → FastAPI → database.
 */
import { expect, test, type Page } from "@playwright/test";

const question = (page: Page) => page.getByRole("textbox", { name: "Your question" });
const sidebar = (page: Page) => page.getByRole("navigation", { name: "Conversations" });

async function ask(page: Page, text: string) {
  await question(page).fill(text);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
}

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("status").filter({ hasText: "Online" })).toBeVisible();
});

test("F1+F2: ask a question, then find the conversation again after a reload", async ({ page }) => {
  await ask(page, "What is AAPL's latest price?");

  const answer = page.getByRole("article", { name: "Assistant" });
  await expect(answer).toContainText("AAPL last traded at");
  await expect(answer.getByRole("list", { name: "Data sources used" })).toContainText("GLOBAL_QUOTE · AAPL");

  await page.reload();
  await sidebar(page).getByRole("button", { name: /^What is AAPL's latest price\?/ }).click();
  await expect(page.getByRole("article", { name: "You" })).toHaveText("What is AAPL's latest price?");
  await expect(page.getByRole("article", { name: "Assistant" })).toContainText("AAPL last traded at");
});

test("F1: follow-up questions stay in the same conversation", async ({ page }) => {
  await ask(page, "hello there");
  await expect(page.getByRole("article", { name: "Assistant" })).toContainText("0 earlier messages");

  await ask(page, "and a follow-up");
  await expect(page.getByRole("article", { name: "Assistant" }).last()).toContainText("2 earlier messages");
  await expect(sidebar(page).getByRole("button", { name: /^hello there/ })).toContainText("4 messages");
});

test("F3: delete a conversation", async ({ page }) => {
  await ask(page, "conversation to delete");
  const entry = sidebar(page).getByRole("button", { name: /^conversation to delete/ });
  await expect(entry).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await sidebar(page).getByRole("button", { name: "Delete conversation “conversation to delete”" }).click();

  await expect(entry).toHaveCount(0);
  await page.reload();
  await expect(sidebar(page).getByRole("button", { name: /^conversation to delete/ })).toHaveCount(0);
});

test("F4+F5: watchlist add, duplicate, ask about a ticker, and remove", async ({ page }) => {
  const symbol = page.getByRole("textbox", { name: "Ticker symbol" });

  await symbol.fill("msft");
  await page.getByRole("textbox", { name: "Note (optional)" }).fill("cloud");
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByRole("button", { name: "Ask about MSFT" })).toBeVisible();

  // Duplicate rejected by the real backend (409), message shown to the user.
  await symbol.fill("MSFT");
  await page.getByRole("button", { name: "Add" }).click();
  await expect(page.getByRole("alert")).toHaveText("MSFT is already on the watchlist");

  await page.getByRole("button", { name: "Ask about MSFT" }).click();
  await expect(question(page)).toHaveValue(/quick overview of MSFT/);
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.getByRole("article", { name: "Assistant" })).toContainText("MSFT last traded at");

  await page.getByRole("button", { name: "Remove MSFT" }).click();
  await expect(page.getByRole("button", { name: "Ask about MSFT" })).toHaveCount(0);
});

test("agent failure: error is shown, question is kept, nothing is saved", async ({ page }) => {
  await ask(page, "please __fail__");

  await expect(page.getByRole("alert")).toContainText("market data service is unavailable");
  await expect(question(page)).toHaveValue("please __fail__");
  await expect(page.getByRole("article", { name: "You" })).toHaveCount(0);
});
