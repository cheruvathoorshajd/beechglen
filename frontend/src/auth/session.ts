// Browser-only "sign in" (design/V2_SCREENS.md → Storage). No accounts, no passwords.
// Every storage call is wrapped: when storage throws (private mode), values live in memory
// for this page load, so the flow still works and onboarding simply shows on each visit.
import { useSyncExternalStore } from "react";

export type Session = { kind: "guest" } | { kind: "local"; name: string };

export const SESSION_KEY = "nexus911:session";
export const ONBOARDED_KEY = "nexus911:onboarded";
export const STEP_KEY = "nexus911:onboarding-step";
const CHANGE_EVENT = "nexus911:session-change";

const memory = { local: new Map<string, string>(), session: new Map<string, string>() };

type Area = "local" | "session";

function storage(area: Area): Storage {
  return area === "local" ? window.localStorage : window.sessionStorage;
}

export function readKey(area: Area, key: string): string | null {
  try {
    const value = storage(area).getItem(key);
    return value ?? memory[area].get(key) ?? null;
  } catch {
    return memory[area].get(key) ?? null;
  }
}

export function writeKey(area: Area, key: string, value: string) {
  memory[area].set(key, value);
  try {
    storage(area).setItem(key, value);
  } catch {
    /* memory only */
  }
}

export function removeKey(area: Area, key: string) {
  memory[area].delete(key);
  try {
    storage(area).removeItem(key);
  } catch {
    /* memory only */
  }
}

function notify() {
  window.dispatchEvent(new Event(CHANGE_EVENT));
}

/* Name validation ------------------------------------------------------------ */

export const NAME_EMPTY = "Enter your name, or continue as a guest.";
export const NAME_INVALID = "Use letters, spaces, apostrophes or hyphens only.";
const NAME_PATTERN = /^[\p{L}\p{M}' ’-]{1,40}$/u;

export type NameCheck = { ok: true; name: string } | { ok: false; error: string };

/** 1–40 characters after trimming: letters, spaces, apostrophes and hyphens only. */
export function validateName(raw: string): NameCheck {
  const name = raw.trim().replace(/\s+/g, " ");
  if (!name) return { ok: false, error: NAME_EMPTY };
  if (!NAME_PATTERN.test(name)) return { ok: false, error: NAME_INVALID };
  return { ok: true, name };
}

/* Session -------------------------------------------------------------------- */

function parse(raw: string | null): Session | null {
  if (!raw) return null;
  try {
    const value = JSON.parse(raw) as Partial<{ kind: string; name: string }>;
    if (value.kind === "guest") return { kind: "guest" };
    if (value.kind === "local" && typeof value.name === "string" && validateName(value.name).ok) {
      return { kind: "local", name: value.name.trim() };
    }
  } catch {
    /* fall through */
  }
  return null;
}

export function getSession(): Session | null {
  return parse(readKey("local", SESSION_KEY));
}

export function setSession(session: Session) {
  writeKey("local", SESSION_KEY, JSON.stringify(session));
  notify();
}

export function clearSession() {
  removeKey("local", SESSION_KEY);
  removeKey("session", STEP_KEY);
  notify();
}

export function onboardedKey(session: Session) {
  return session.kind === "guest" ? ONBOARDED_KEY : `${ONBOARDED_KEY}:${session.name.toLowerCase()}`;
}

export function isOnboarded(session: Session) {
  return readKey("local", onboardedKey(session)) === "1";
}

export function markOnboarded(session: Session) {
  writeKey("local", onboardedKey(session), "1");
  removeKey("session", STEP_KEY);
  notify();
}

export function clearOnboarded(session: Session) {
  removeKey("local", onboardedKey(session));
  removeKey("session", STEP_KEY);
  notify();
}

export function displayName(session: Session | null) {
  return session && session.kind === "local" ? session.name : "Guest";
}

/** The session, re-read on the storage event so two tabs stay in step. */
export function useSession(): Session | null {
  const raw = useSyncExternalStore(subscribe, () => readKey("local", SESSION_KEY) ?? "", () => "");
  return parse(raw || null);
}

/** Re-renders when onboarding state changes (same tab or another tab). */
export function useSessionVersion(): string {
  return useSyncExternalStore(
    subscribe,
    () => {
      const session = getSession();
      return `${readKey("local", SESSION_KEY) ?? ""}|${session && isOnboarded(session) ? 1 : 0}`;
    },
    () => "",
  );
}

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener(CHANGE_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(CHANGE_EVENT, callback);
  };
}

/** Test helper: forget the in-memory fallback. */
export function resetMemoryForTests() {
  memory.local.clear();
  memory.session.clear();
}
