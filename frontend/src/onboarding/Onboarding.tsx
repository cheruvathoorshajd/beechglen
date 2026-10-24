import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError, api, errorMessage } from "../api/client";
import { Bloom, Button, ChoiceCard, ConfidenceBar, Icon, Segmented, SpecLabel, Wordmark, nextIndex, type IconName } from "../ui";
import { STEP_KEY, getSession, markOnboarded, readKey, writeKey } from "../auth/session";
import { BandChip, NewInfoBadge } from "../components/console/chips";
import { useFocusTrap } from "../hooks/useFocusTrap";
import { BAND_MEANING } from "../lib/format";
import "./onboarding.css";

type StepId = "what" | "read" | "start";
const FLOW: StepId[] = ["what", "read", "start"];
const RAIL = ["What it does", "How to read it", "Choose how to start", "Console"];
const SPEC: Record<StepId, string> = { what: "What it does", read: "How to read it", start: "Choose how to start" };

type Choice = "demo" | "console";
type Speed = "5" | "10" | "20";
type Server = "checking" | "up" | "down";

const METRICS_TIMEOUT_MS = 4000;

function initialStep(): number {
  const saved = readKey("session", STEP_KEY) as StepId | null;
  const index = saved ? FLOW.indexOf(saved) : -1;
  return index >= 0 ? index : 0;
}

function Point({ icon, title, children }: { icon: IconName; title: string; children: React.ReactNode }) {
  return (
    <li>
      <Icon name={icon} />
      <div>
        <b>{title}</b>
        {children}
      </div>
    </li>
  );
}

/** /welcome: the three-step intro (design/V2_SCREENS.md → Onboarding). */
export default function Onboarding() {
  const navigate = useNavigate();
  const session = getSession();
  const [step, setStep] = useState(initialStep);
  const [choice, setChoice] = useState<Choice>("demo");
  const [speed, setSpeed] = useState<Speed>("10");
  const [server, setServer] = useState<Server>("checking");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const dialog = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const id = FLOW[step];

  const finish = useCallback(() => {
    const current = getSession();
    if (current) markOnboarded(current);
    navigate("/operator", { replace: true });
  }, [navigate]);

  useFocusTrap(dialog, finish);

  useEffect(() => {
    writeKey("session", STEP_KEY, id);
    heading.current?.focus({ preventScroll: true });
  }, [id]);

  const checkServer = useCallback(async () => {
    setServer("checking");
    try {
      await api.metrics(METRICS_TIMEOUT_MS);
      setServer("up");
    } catch {
      setServer("down");
      setChoice("console");
    }
  }, []);

  useEffect(() => {
    if (id === "start") void checkServer();
  }, [id, checkServer]);

  const runDemo = async () => {
    setStarting(true);
    setStartError(null);
    try {
      await api.reset();
      try {
        await api.startSim({ scenario_id: "mass_ave_robbery", speed: Number(speed) });
      } catch (error) {
        // A replay that is already running counts as started.
        if (!(error instanceof ApiError && /already running/i.test(error.message))) throw error;
      }
      finish();
    } catch (error) {
      setStartError(`The demo didn't start: ${errorMessage(error)}`);
      setStarting(false);
    }
  };

  const next = () => {
    if (step < FLOW.length - 1) {
      setStep(step + 1);
      return;
    }
    if (choice === "demo") void runDemo();
    else finish();
  };

  const demoDisabled = server !== "up";
  const cards: Choice[] = ["demo", "console"];
  const onCardsKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const current = cards.indexOf(choice);
    const target = nextIndex(event.key, current, cards.length);
    if (target === null) return;
    event.preventDefault();
    let pick = cards[target];
    if (pick === "demo" && demoDisabled) pick = "console";
    setChoice(pick);
    event.currentTarget.querySelectorAll<HTMLElement>('[role="radio"].choice')[cards.indexOf(pick)]?.focus();
  };

  const primaryLabel = step < 2 ? "Continue" : choice === "demo" ? "Run the demo" : "Open the console";

  return (
    <div className="ob" ref={dialog} role="dialog" aria-modal="true" aria-label="Welcome to Nexus911">
      <Bloom />
      <div className="ob-progress" aria-hidden="true">
        <i style={{ width: `${Math.round((step / 3) * 100)}%` }} />
      </div>

      <aside className="ob-rail">
        <Wordmark />
        <ol className="ob-steps">
          {RAIL.map((label, index) => (
            <li key={label} className={index === step ? "on" : index < step ? "done" : ""} aria-current={index === step ? "step" : undefined}>
              <span className="n num">{index < step ? <Icon name="tick" /> : String(index + 1).padStart(2, "0")}</span>
              {label}
            </li>
          ))}
        </ol>
        <p className="cap">About a minute. You can replay this from the console.</p>
      </aside>

      <div className="ob-main">
        <div className="ob-body" key={id}>
          <SpecLabel k={`Step ${step + 1} of 3`} rest={[SPEC[id]]} />

          {id === "what" && (
            <>
              <h1 className="ob-h" tabIndex={-1} ref={heading}>
                Many calls. One incident.
              </h1>
              <p className="ob-lede">
                {session?.kind === "local" ? `Welcome, ${session.name}.` : "Welcome to Nexus911."} When many people call about the
                same emergency, Nexus911 links their calls into one incident, weighs what they say, and puts the calls with new
                information first.
              </p>
              <ul className="ob-points">
                <Point icon="merge" title="Calls link into incidents.">
                  <span>Place, time, type and details give each link a score. Strong matches link on their own; weaker ones wait for you.</span>
                </Point>
                <Point icon="alert" title="New information rises.">
                  <span>A new weapon, injury, location or hazard goes to the top. Repeats sink, but no call ever leaves the queue.</span>
                </Point>
                <Point icon="shield" title="You stay in control.">
                  <span>Confirm or split any link. Every decision is logged.</span>
                </Point>
              </ul>
            </>
          )}

          {id === "read" && (
            <>
              <h1 className="ob-h" tabIndex={-1} ref={heading}>
                Every fact shows its evidence.
              </h1>
              <p className="ob-lede">
                Each detail lists every value callers reported, with its weighted share and the number of callers behind it. When
                callers disagree, it's flagged for you to decide.
              </p>
              <ul className="ob-points">
                <Point icon="users" title="Share and sources.">
                  <span>
                    From the robbery demo: raw counts would say 70–30, but hearsay and a repeat caller count for less.
                  </span>
                  <div className="eg">
                    <ConfidenceBar label="Jacket · white" value={0.83} sources={7} tone="ok" />
                    <ConfidenceBar label="Jacket · black" value={0.17} sources={3} tone="soft" />
                  </div>
                </Point>
                <Point icon="alert" title="Contested.">
                  <span>The top value has under 70% and the runner-up at least 20%, like the SUV's color in the Pike crash.</span>
                  <div className="eg-row">
                    <span className="contested">△ Contested</span>
                    <span className="text-[13.5px] text-ink">SUV color: silver or white</span>
                  </div>
                </Point>
                <Point icon="radio" title="NEW INFO.">
                  <span>Why a call jumped the queue, in words.</span>
                  <div className="eg-row">
                    <NewInfoBadge reasons={["new_weapon", "new_injury"]} />
                    <NewInfoBadge reasons={["new_location", "new_hazard"]} />
                  </div>
                </Point>
                <Point icon="merge" title="Bands.">
                  <ul className="eg-bands">
                    {(["auto", "suggest", "new", "confirmed"] as const).map((band) => (
                      <li key={band}>
                        <BandChip band={band} /> <span>{BAND_MEANING[band]}</span>
                      </li>
                    ))}
                  </ul>
                </Point>
              </ul>
              <div className="proto-note">
                <Icon name="alert" />
                <span>
                  <b>This is a prototype.</b> Every call is synthetic, and no real emergency services are contacted.
                </span>
              </div>
            </>
          )}

          {id === "start" && (
            <>
              <h1 className="ob-h" tabIndex={-1} ref={heading}>
                How would you like to start?
              </h1>
              <p className="ob-lede">Watch an incident come together, or go straight to the console.</p>
              <div className="ob-cards" role="radiogroup" aria-label="How to start" onKeyDown={onCardsKey}>
                <ChoiceCard
                  radio
                  icon="car"
                  tag="Recommended"
                  title="Run the Mass Ave robbery demo"
                  body="Eleven calls about one robbery, then a fire a block away. Watch duplicates sink and the new emergency jump to the top."
                  selected={choice === "demo"}
                  disabled={demoDisabled}
                  onSelect={() => setChoice("demo")}
                >
                  <div className="mt-2.5 grid gap-1.5">
                    <Segmented
                      label="Demo speed"
                      value={speed}
                      onChange={setSpeed}
                      disabled={demoDisabled}
                      options={[
                        { value: "5", label: "5×" },
                        { value: "10", label: "10×" },
                        { value: "20", label: "20×" },
                      ]}
                    />
                    <span className="cap">This clears the console, then replays the calls.</span>
                  </div>
                </ChoiceCard>
                <ChoiceCard
                  radio
                  icon="grid"
                  title="Open the operator console"
                  body="Go straight to the queue. You can run any scenario from Sim."
                  selected={choice === "console"}
                  onSelect={() => setChoice("console")}
                />
              </div>

              {server === "checking" && <p className="server cap">Checking the server…</p>}
              {server === "up" && (
                <p className="server cap">
                  <i className="dot" aria-hidden="true" />
                  Server reachable
                </p>
              )}
              {server === "down" && (
                <div className="server down cap" role="alert">
                  <i className="dot" aria-hidden="true" />
                  <span>Can't reach the Nexus911 server, so the demo can't start. You can still open the console, or try again.</span>
                  <Button variant="ghost" size="sm" onClick={() => void checkServer()}>
                    Try again
                  </Button>
                </div>
              )}
              {startError && (
                <div className="server down cap" role="alert">
                  <i className="dot" aria-hidden="true" />
                  <span>{startError}</span>
                  <Button variant="ghost" size="sm" onClick={finish}>
                    Open the console instead
                  </Button>
                </div>
              )}
            </>
          )}
        </div>

        <footer className="ob-foot">
          <Button variant="quiet" onClick={() => setStep(step - 1)} style={{ visibility: step === 0 ? "hidden" : "visible" }} aria-hidden={step === 0} tabIndex={step === 0 ? -1 : 0}>
            Back
          </Button>
          <div className="right">
            <Button variant="quiet" onClick={finish}>
              Skip intro
            </Button>
            <Button
              variant="primary"
              onClick={next}
              disabled={starting || (step === 2 && choice === "demo" && demoDisabled)}
              aria-busy={starting || undefined}
            >
              {starting ? (
                <>
                  <span className="spinner" aria-hidden="true" /> Starting the demo…
                </>
              ) : (
                <>
                  {primaryLabel} <Icon name="arrow" />
                </>
              )}
            </Button>
          </div>
        </footer>
      </div>
    </div>
  );
}
