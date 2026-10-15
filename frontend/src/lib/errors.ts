import { ApiError } from "../api/client";

/** A message that is safe and useful to show the user. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return "Something went wrong. Please try again.";
}
