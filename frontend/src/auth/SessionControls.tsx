import { useNavigate } from "react-router-dom";
import { Button } from "../ui";
import { signOut } from "./guards";
import { clearOnboarded, displayName, useSession } from "./session";

/** Console header: who chip, Replay intro, Sign out (design/V2_SCREENS.md → Console header). */
export function SessionControls() {
  const session = useSession();
  const navigate = useNavigate();
  if (!session) return null;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="inline-flex items-center gap-2 rounded border border-rule-soft px-2.5 py-1.5 font-mono text-[11.5px] tracking-[0.08em] text-ink-soft">
        {session.kind === "guest" ? "Browsing as" : "Signed in as"} <b className="font-medium text-ink">{displayName(session)}</b>
      </span>
      <Button
        variant="quiet"
        size="sm"
        onClick={() => {
          clearOnboarded(session);
          navigate("/welcome");
        }}
      >
        Replay intro
      </Button>
      <Button
        variant="quiet"
        size="sm"
        onClick={() => signOut(navigate)}
      >
        Sign out
      </Button>
    </div>
  );
}
