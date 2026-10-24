import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { RequireConsole, RequireSession, SignedOutOnly } from "./auth/guards";
import SignIn from "./auth/SignIn";
import { ConsoleLayout } from "./components/console/shell";
import Landing from "./landing/Landing";
import Onboarding from "./onboarding/Onboarding";
import Operator from "./pages/Operator";
import Officer from "./pages/Officer";
import Sim from "./pages/Sim";
import "./components/console/console.css";

const consolePage = (page: ReactNode) => (
  <RequireConsole>
    <ConsoleLayout>{page}</ConsoleLayout>
  </RequireConsole>
);

/** Landing → Sign in (or guest) → Onboarding → Console (design/V2_SCREENS.md → Flow and routes). */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route
        path="/signin"
        element={
          <SignedOutOnly>
            <SignIn />
          </SignedOutOnly>
        }
      />
      <Route
        path="/welcome"
        element={
          <RequireSession>
            <Onboarding />
          </RequireSession>
        }
      />
      <Route path="/operator" element={consolePage(<Operator />)} />
      <Route path="/officer" element={consolePage(<Officer />)} />
      <Route path="/sim" element={consolePage(<Sim />)} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
