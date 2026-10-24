import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, Disc, Field, Icon, SpecLabel, Wordmark, buttonClass, type IconName } from "../ui";
import { isOnboarded, setSession, validateName, type Session } from "./session";
import "./auth.css";

const PROOF: [IconName, string, string][] = [
  ["shield", "Claims cite the caller.", "Every fact shows its confidence and sources."],
  ["alert", "New information rises.", "A new weapon, injury or hazard goes to the top."],
  ["merge", "You decide.", "Confirm or split any link, and every decision is logged."],
];

/** /signin: name only, kept in this browser; or continue as a guest. */
export default function SignIn() {
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    input.current?.focus({ preventScroll: true });
  }, []);

  const enter = (session: Session) => {
    setSession(session);
    navigate(isOnboarded(session) ? "/operator" : "/welcome");
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    const check = validateName(name);
    if (!check.ok) {
      setError(check.error);
      input.current?.focus();
      return;
    }
    enter({ kind: "local", name: check.name });
  };

  return (
    <div className="auth enter">
      <aside className="auth-story gut">
        <Disc />
        <Wordmark to="/" className="relative" />
        <h2>
          Many calls. One <em>verified</em> incident.
        </h2>
        <ul className="proof">
          {PROOF.map(([icon, title, text]) => (
            <li key={title}>
              <Icon name={icon} />
              <span>
                <b>{title}</b> {text}
              </span>
            </li>
          ))}
        </ul>
        <Link to="/" className={buttonClass("quiet", "sm", false, "auth-home")}>
          ← Nexus911 home
        </Link>
      </aside>

      <main className="auth-form gut">
        <form className="inner" onSubmit={onSubmit} noValidate aria-labelledby="signin-h">
          <SpecLabel k="Sign in" rest={["Prototype"]} />
          <h1 id="signin-h">Who's on the console?</h1>
          <p className="lede">Tell us your name so we can greet you, or continue as a guest. Both get every feature.</p>
          <Field
            ref={input}
            id="name"
            name="name"
            label="Your name"
            autoComplete="name"
            required
            maxLength={40}
            value={name}
            error={error ?? undefined}
            onChange={(event) => {
              setName(event.target.value);
              if (error) setError(null);
            }}
          />
          <Button type="submit" variant="primary" block icon="arrow">
            Continue
          </Button>
          <div className="or">or</div>
          <div className="grid gap-2">
            <Button variant="ghost" block onClick={() => enter({ kind: "guest" })}>
              Continue as guest
            </Button>
            <p className="cap text-center">Guests can use every feature.</p>
          </div>
          <p className="cap note">
            Your name is kept in this browser only. There's no password, because this prototype has no accounts.
          </p>
        </form>
      </main>
    </div>
  );
}
