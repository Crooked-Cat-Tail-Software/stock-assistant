import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library only auto-cleans when test globals are enabled; we import
// from "vitest" explicitly instead, so unmount rendered trees here.
afterEach(() => cleanup());
