import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";
import { renderAt } from "../test/render";
import App from "../App";
import {
  NAME_EMPTY,
  NAME_INVALID,
  ONBOARDED_KEY,
  SESSION_KEY,
  clearOnboarded,
  clearSession,
  displayName,
  getSession,
  isOnboarded,
  markOnboarded,
  onboardedKey,
  setSession,
  validateName,
} from "./session";

vi.mock("../components/console/IncidentMap", () => ({ IncidentMap: () => <div data-testid="map-stub" /> }));

describe("session.ts", () => {
  it("stores guests and named people, and clears them", () => {
    expect(getSession()).toBeNull();
    setSession({ kind: "guest" });
    expect(window.localStorage.getItem(SESSION_KEY)).toBe('{"kind":"guest"}');
    expect(getSession()).toEqual({ kind: "guest" });
    setSession({ kind: "local", name: "Dennis" });
    expect(getSession()).toEqual({ kind: "local", name: "Dennis" });
    expect(displayName(getSession())).toBe("Dennis");
    clearSession();
    expect(getSession()).toBeNull();
    expect(displayName(null)).toBe("Guest");
  });

  it("keeps the onboarded flag per person, lowercased", () => {
    const dennis = { kind: "local", name: "Dennis" } as const;
    expect(onboardedKey({ kind: "guest" })).toBe(ONBOARDED_KEY);
    expect(onboardedKey(dennis)).toBe("nexus911:onboarded:dennis");
    expect(isOnboarded(dennis)).toBe(false);
    markOnboarded(dennis);
    expect(isOnboarded(dennis)).toBe(true);
    expect(isOnboarded({ kind: "local", name: "Arvind" })).toBe(false);
    clearOnboarded(dennis);
    expect(isOnboarded(dennis)).toBe(false);
  });

  it("ignores corrupt stored sessions", () => {
    window.localStorage.setItem(SESSION_KEY, "{not json");
    expect(getSession()).toBeNull();
    window.localStorage.setItem(SESSION_KEY, '{"kind":"local","name":"<script>"}');
    expect(getSession()).toBeNull();
  });

  it("keeps working when storage throws (private mode)", () => {
    const denied = () => {
      throw new DOMException("denied", "SecurityError");
    };
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(denied);
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(denied);
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(denied);

    expect(getSession()).toBeNull();
    setSession({ kind: "local", name: "Kaushik" });
    expect(getSession()).toEqual({ kind: "local", name: "Kaushik" });
    markOnboarded({ kind: "local", name: "Kaushik" });
    expect(isOnboarded({ kind: "local", name: "Kaushik" })).toBe(true);
    clearSession();
    expect(getSession()).toBeNull();
  });
});

describe("name validation", () => {
  it.each([
    ["", NAME_EMPTY],
    ["   ", NAME_EMPTY],
    ["R2-D2", NAME_INVALID],
    ["dennis@example.com", NAME_INVALID],
    ["a".repeat(41), NAME_INVALID],
  ])("%j is rejected", (raw, error) => {
    expect(validateName(raw)).toEqual({ ok: false, error });
  });

  it.each([
    ["Dennis", "Dennis"],
    ["  Mary-Kate  O'Neil ", "Mary-Kate O'Neil"],
    ["José Ramírez", "José Ramírez"],
    ["a".repeat(40), "a".repeat(40)],
  ])("%j is accepted", (raw, name) => {
    expect(validateName(raw)).toEqual({ ok: true, name });
  });
});

describe("route guard", () => {
  it("sends a visitor without a session from the console to sign-in", () => {
    renderAt("/operator", <App />);
    expect(screen.getByRole("heading", { name: "Who's on the console?" })).toBeTruthy();
  });

  it("sends a visitor without a session from /welcome to sign-in", () => {
    renderAt("/welcome", <App />);
    expect(screen.getByRole("heading", { name: "Who's on the console?" })).toBeTruthy();
  });

  it("sends a session that hasn't onboarded to /welcome", () => {
    setSession({ kind: "guest" });
    renderAt("/sim", <App />);
    expect(screen.queryByRole("heading", { name: "Replay a scenario." })).toBeNull();
    expect(screen.getByText(/STEP 1 OF 3|Onboarding/i)).toBeTruthy();
  });

  it("sends /signin with a session to the console", async () => {
    setSession({ kind: "guest" });
    markOnboarded({ kind: "guest" });
    renderAt("/signin", <App />);
    expect(await screen.findByRole("heading", { name: /Queue/ })).toBeTruthy();
  });

  it("sends unknown routes to the landing", () => {
    renderAt("/nope", <App />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Every call heard. New facts first.");
  });
});

describe("sign in", () => {
  it("shows the empty and invalid errors and returns focus to the field", () => {
    renderAt("/signin", <App />);
    const input = screen.getByLabelText("Your name");
    fireEvent.click(screen.getByRole("button", { name: /Continue$/ }));
    expect(screen.getByText(NAME_EMPTY)).toBeTruthy();
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(document.activeElement).toBe(input);

    fireEvent.change(input, { target: { value: "R2-D2" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue$/ }));
    expect(screen.getByText(NAME_INVALID)).toBeTruthy();
    expect(document.activeElement).toBe(input);
  });

  it("a valid name starts the intro; a returning person goes straight to the console", async () => {
    renderAt("/signin", <App />);
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "Dennis" } });
    fireEvent.click(screen.getByRole("button", { name: /Continue$/ }));
    expect(getSession()).toEqual({ kind: "local", name: "Dennis" });
    expect(screen.queryByRole("heading", { name: "Who's on the console?" })).toBeNull();
  });

  it("continue as guest", () => {
    renderAt("/signin", <App />);
    fireEvent.click(screen.getByRole("button", { name: "Continue as guest" }));
    expect(getSession()).toEqual({ kind: "guest" });
  });
});

describe("console header", () => {
  it("shows who is signed in, replays the intro and signs out", async () => {
    setSession({ kind: "local", name: "Dennis" });
    markOnboarded({ kind: "local", name: "Dennis" });
    renderAt("/operator", <App />);
    expect(await screen.findByText("Dennis")).toBeTruthy();
    expect(screen.getByText(/Signed in as/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Replay intro" }));
    expect(isOnboarded({ kind: "local", name: "Dennis" })).toBe(false);
  });

  it("guests browse as Guest and can sign out", async () => {
    setSession({ kind: "guest" });
    markOnboarded({ kind: "guest" });
    renderAt("/officer", <App />);
    expect(await screen.findByText(/Browsing as/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(getSession()).toBeNull();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Every call heard. New facts first.");
  });
});
