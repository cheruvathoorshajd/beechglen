import type { NavigateFunction } from "react-router-dom";

export interface StartTargets {
  start: string;
  startLabel: string;
  demo: string;
  signIn: string | null;
  continueAsGuest: (navigate: NavigateFunction) => void;
}

/** Where the landing CTAs go. Until sign-in exists (D4), everything opens the console. */
export function useStartTargets(): StartTargets {
  return {
    start: "/operator",
    startLabel: "Get started",
    demo: "/operator",
    signIn: "/operator",
    continueAsGuest: (navigate) => navigate("/operator"),
  };
}
