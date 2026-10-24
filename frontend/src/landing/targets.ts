import type { NavigateFunction } from "react-router-dom";
import { isOnboarded, setSession, useSession } from "../auth/session";

export interface StartTargets {
  start: string;
  startLabel: string;
  demo: string;
  signIn: string | null;
  continueAsGuest: (navigate: NavigateFunction) => void;
}

/** Where the landing CTAs go (design/V2_SCREENS.md → Landing). */
export function useStartTargets(): StartTargets {
  const session = useSession();
  return {
    start: session ? "/operator" : "/signin",
    startLabel: session ? "Open the console" : "Get started",
    demo: session ? "/welcome" : "/signin",
    signIn: session ? null : "/signin",
    continueAsGuest: (navigate) => {
      const guest = { kind: "guest" } as const;
      setSession(guest);
      navigate(isOnboarded(guest) ? "/operator" : "/welcome");
    },
  };
}
