import { afterEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import { resetMemoryForTests } from "../auth/session";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  window.localStorage.clear();
  window.sessionStorage.clear();
  resetMemoryForTests();
});

// jsdom has no matchMedia; components read it for reduced motion.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}
