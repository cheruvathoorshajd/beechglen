import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { clearSession, getSession, isOnboarded, useSessionVersion } from "./session";

// While signing out, the console guard must not redirect to /signin before the
// navigation to / lands (the two updates can render in either order).
let signingOut = false;

/** Clears the session and goes to the landing page. */
export function signOut(navigate: (to: string, options?: { replace?: boolean }) => void) {
  signingOut = true;
  navigate("/", { replace: true });
  clearSession();
}

/** Called by the landing page once it is showing. */
export function endSignOut() {
  signingOut = false;
}

/** /operator, /officer, /sim: no session → /signin; not onboarded → /welcome. */
export function RequireConsole({ children }: { children: ReactNode }) {
  useSessionVersion();
  const session = getSession();
  if (!session) return signingOut ? null : <Navigate to="/signin" replace />;
  if (!isOnboarded(session)) return <Navigate to="/welcome" replace />;
  return <>{children}</>;
}

/** /welcome: no session → /signin. */
export function RequireSession({ children }: { children: ReactNode }) {
  useSessionVersion();
  if (!getSession()) return <Navigate to="/signin" replace />;
  return <>{children}</>;
}

/** /signin: with a session → /operator (whose guard sends a new person to /welcome). */
export function SignedOutOnly({ children }: { children: ReactNode }) {
  useSessionVersion();
  if (getSession()) return <Navigate to="/operator" replace />;
  return <>{children}</>;
}
