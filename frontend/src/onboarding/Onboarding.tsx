import { useNavigate } from "react-router-dom";
import { Button, SpecLabel, Wordmark } from "../ui";
import { getSession, markOnboarded } from "../auth/session";

// D4 placeholder: the three-step wizard replaces this in D5.
export default function Onboarding() {
  const navigate = useNavigate();
  return (
    <main className="grid min-h-screen place-content-center gap-6 p-8">
      <Wordmark />
      <SpecLabel k="Onboarding" rest={["Coming in D5"]} />
      <h1 className="font-serif text-4xl font-medium">Many calls. One incident.</h1>
      <Button
        variant="primary"
        icon="arrow"
        onClick={() => {
          const session = getSession();
          if (session) markOnboarded(session);
          navigate("/operator");
        }}
      >
        Open the console
      </Button>
    </main>
  );
}
