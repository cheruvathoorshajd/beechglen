import { Link, useNavigate } from "react-router-dom";
import { ChoiceCard, Disc, Icon, SpecLabel, Wordmark, buttonClass, type IconName } from "../ui";
import { useStartTargets } from "./targets";
import "./landing.css";

const REPO_URL = "https://github.com/cheruvathoorshajd/beechglen#readme";
const HACKATHON = "the hackathon";

const NAV = [
  ["problem", "Problem"],
  ["how", "How it works"],
  ["novelties", "Novelties"],
  ["massachusetts", "Massachusetts"],
  ["limits", "Limitations"],
] as const;

const STATS = [
  ["10th", "A new emergency nearby can wait in the same queue as the tenth call about the last one."],
  ["7 vs 3", "Callers disagree about what they saw, and a raw count can't say whose account to trust."],
  ["Exit 8 = 63", "MassDOT renumbered highway exits, and callers on the Pike still use both numbers."],
] as const;

const FLOW = [
  ["Extract.", "Claude turns the call into claims, each citing the caller's words."],
  ["Verify.", "A claim whose quote isn't in the transcript is rejected."],
  ["Locate.", "Massachusetts streets, towns, landmarks and old or new exit numbers."],
  ["Link.", "Place, time, type and details give a match score: auto, suggest or new."],
  ["Weigh.", "Reliability, recency and independence decide each value's share."],
  ["Prioritize.", "New information rises. Repeats sink, but stay in the queue."],
  ["Dispatch.", "One package with confidence and sources on every field."],
] as const;

const NOVELTIES: [IconName, string, string, string][] = [
  ["share", "Claim-level knowledge graph.", "Every statement is its own node with its caller, quote and weight, so conflicting accounts are kept and weighed.", "Claims, not records"],
  ["shield", "Quote-grounded guard.", "An AI-extracted fact must cite the transcript word for word, or it's rejected.", "Hallucination check"],
  ["alert", "Information-gain priority.", "Repeats sink, new facts rise, and a new weapon, injury, location or hazard always escalates.", "Severity × novelty"],
  ["users", "Independence-aware weighting.", "Hearsay and repeat callers count for less, so an echoed rumor can't outvote eyewitnesses.", "7–3 becomes 83–17"],
  ["merge", "Explainable linking.", "Auto-link, suggest or new, with every score component visible and one-click confirm or split.", "Three bands"],
  ["pin", "Massachusetts-aware.", "Town ambiguity, old and new exit numbers, MBTA, campus and State Police routing, transfers, many languages.", "Built for MA"],
];

// README "Massachusetts specifics", as written.
const MASSACHUSETTS: [string, string, string][] = [
  [
    "Same street name in many towns",
    'Town-aware gazetteer, nearest-to-device disambiguation, "Which town?" prompt, never auto-links an ambiguous location',
    "Washington St (Boston, Brookline, Somerville), Massachusetts Ave (Boston, Cambridge, Arlington)",
  ],
  ["Exits renumbered from sequential to mile-based; callers use both", "Accepts old and new exit numbers, mile markers and route nicknames", "I-90 Exit 63 = old Exit 8 (Palmer)"],
  [
    "Calls answered by one center and transferred to another",
    'Transfer stored as a graph edge; incident shows "Transferred from …, context preserved"',
    "Pike scenario transfer from `palmer-local` to `msp-pike`",
  ],
  ["Many agencies", "Routing to local PD, State Police, MBTA Transit Police, campus police, fire and EMS", "`agencies.json`, `landmarks.json`"],
  [
    "Multilingual callers",
    "Quotes stay in the original language for grounding; values are canonical English, so linking works across languages",
    "Spanish and Portuguese calls",
  ],
  ["Text-to-911", "`channel = text`; short texts still extract and link", "Pike scenario text"],
  ["Surge events", "Mass-event mode: stricter auto-link, wider time window", "Toggle on /sim"],
];

const LIMITS = [
  ["Synthetic calls only.", "No real 911, CAD, NG911 or speech recognition integration."],
  ["Heuristic weights.", "Thresholds and role priors haven't been validated with dispatch professionals."],
  ["Simplified subjects.", "Calls are aligned to one primary suspect and one vehicle."],
  ["Demo map data.", "Small Massachusetts samples with approximate coordinates."],
  ["Illustrative units.", "Recommended units aren't real dispatch protocols."],
  ["Memory only.", "State resets on restart, and latency isn't benchmarked."],
] as const;

/** Renders README text, turning `code` spans into <code>. */
function Rich({ text }: { text: string }) {
  return (
    <>
      {text.split(/(`[^`]+`)/).map((part, index) =>
        part.startsWith("`") ? <code key={index}>{part.slice(1, -1)}</code> : <span key={index}>{part}</span>,
      )}
    </>
  );
}

export default function Landing() {
  const targets = useStartTargets();
  const navigate = useNavigate();

  return (
    <div className="lp enter">
      <header className="lp-mast gut">
        <Wordmark to="/" />
        <nav className="lp-nav" aria-label="Sections">
          {NAV.map(([id, label]) => (
            <a key={id} href={`#${id}`}>
              {label}
            </a>
          ))}
        </nav>
        <div className="lp-mast-act">
          {targets.signIn && (
            <Link className={buttonClass("ghost", "sm")} to={targets.signIn}>
              Sign in
            </Link>
          )}
          <Link className={buttonClass("primary", "sm")} to={targets.start}>
            {targets.startLabel}
          </Link>
        </div>
      </header>

      <main>
        <section className="lp-hero gut" aria-labelledby="hero-h">
          <Disc />
          <SpecLabel k="Claim-weighted 911" rest={["Prototype"]} />
          <h1 id="hero-h">
            Every call heard. <em>New facts</em> first.
          </h1>
          <div className="lp-hero-grid">
            <p className="lp-lede">
              When many people call about one emergency, Nexus911 links the duplicates into one incident, weighs conflicting
              accounts by their evidence, and moves the call with new information to the top. Operators confirm or split every
              link.
            </p>
            <div className="lp-cta">
              <Link className={buttonClass("primary")} to={targets.demo}>
                Run the demo <Icon name="arrow" />
              </Link>
              <a className={buttonClass("ghost")} href="#how">
                How it works
              </a>
            </div>
          </div>
          <div className="lp-meta">
            <span>Quote-grounded claims</span>
            <span>Three-band linking</span>
            <span>Information-gain priority</span>
            <span>Massachusetts-aware</span>
          </div>
        </section>

        <section className="lp-sec gut" id="problem" aria-labelledby="h-problem">
          <div className="lp-sec-h">
            <SpecLabel k="The problem" />
            <h2 className="sec-t" id="h-problem">
              Big incidents arrive as many small, separate calls.
            </h2>
          </div>
          <div className="lp-stats">
            {STATS.map(([figure, text]) => (
              <div className="lp-stat" key={figure}>
                <div className="fig">{figure}</div>
                <p>{text}</p>
              </div>
            ))}
          </div>
          <p className="lp-risk">
            Language models can help sort calls, but they can also <em>invent details</em>. Nexus911 keeps a fact only when it
            cites the caller's own words.
          </p>
        </section>

        <section className="lp-sec gut" id="how" aria-labelledby="h-how">
          <div className="lp-sec-h">
            <SpecLabel k="How it works" rest={["Seven steps, every call"]} />
            <h2 className="sec-t" id="h-how">
              From many calls to one incident.
            </h2>
          </div>
          <ol className="lp-flow">
            {FLOW.map(([title, text]) => (
              <li key={title}>
                <b>{title}</b>
                <span>{text}</span>
              </li>
            ))}
          </ol>
          <p className="lp-results">
            On the three demo scenarios: 28 calls → 5 incidents · 5 of 5 new incidents surfaced · 10 of 10 new-information calls
            flagged · synthetic data
          </p>
        </section>

        <section className="lp-sec gut" id="novelties" aria-labelledby="h-nov">
          <div className="lp-sec-h">
            <SpecLabel k="What's new" rest={["Six ideas"]} />
            <h2 className="sec-t" id="h-nov">
              Built to sort the calls, and to show its work.
            </h2>
          </div>
          <div className="lp-grid">
            {NOVELTIES.map(([icon, title, text, tagline]) => (
              <article className="lp-feat" key={title}>
                <span className="icon-tile">
                  <Icon name={icon} />
                </span>
                <h3>{title}</h3>
                <p>{text}</p>
                <span className="tagline">{tagline}</span>
              </article>
            ))}
          </div>
        </section>

        <section className="lp-band" aria-label="The principle behind Nexus911">
          <div className="gut">
            <blockquote>
              No call is ever <em>dropped</em>. Nexus911 reorders and annotates the queue; it never hides a call.
            </blockquote>
            <p className="cap">The principle behind Nexus911</p>
          </div>
        </section>

        <section className="lp-sec gut" id="massachusetts" aria-labelledby="h-ma">
          <div className="lp-sec-h">
            <SpecLabel k="Built for Massachusetts" />
            <h2 className="sec-t" id="h-ma">
              Local problems, handled on purpose.
            </h2>
          </div>
          <div className="tbl-wrap">
            <table className="cmp">
              <thead>
                <tr>
                  <th scope="col">Problem</th>
                  <th scope="col" className="us">
                    How Nexus911 handles it
                  </th>
                  <th scope="col">Demo</th>
                </tr>
              </thead>
              <tbody>
                {MASSACHUSETTS.map(([problem, handling, demo]) => (
                  <tr key={problem}>
                    <th scope="row">{problem}</th>
                    <td className="us">
                      <Rich text={handling} />
                    </td>
                    <td>
                      <Rich text={demo} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="lp-sec gut" id="limits" aria-labelledby="h-lim">
          <div className="lp-sec-h">
            <SpecLabel k="Known limitations" />
            <h2 className="sec-t" id="h-lim">
              What this prototype can't do yet.
            </h2>
          </div>
          <ul className="lp-limits">
            {LIMITS.map(([title, text]) => (
              <li key={title}>
                <span>
                  <b>{title}</b> {text}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="lp-sec gut" id="start" aria-labelledby="h-start">
          <div className="lp-sec-h">
            <SpecLabel k="Get started" />
            <h2 className="sec-t" id="h-start">
              How would you like to start?
            </h2>
          </div>
          <div className="lp-start">
            <ChoiceCard
              selected
              tag="Fastest"
              title="Continue as guest"
              body="Use every feature right away. Nothing to fill in."
              go="Continue →"
              onSelect={() => targets.continueAsGuest(navigate)}
            />
            <ChoiceCard
              title="Sign in with your name"
              body="We'll greet you by name and remember your intro in this browser."
              go="Sign in →"
              onSelect={() => navigate(targets.signIn ?? targets.start)}
            />
            <ChoiceCard
              title="Read how it works first"
              body="The seven-step pipeline, from first call to dispatch."
              go="How it works ↑"
              onSelect={() => document.getElementById("how")?.scrollIntoView()}
            />
          </div>
        </section>
      </main>

      <footer className="lp-colophon gut">
        <Wordmark />
        <p className="cap">
          • Emergency dispatching, simplified • · Built for {HACKATHON} · MIT licence · Synthetic data only ·{" "}
          <a href={REPO_URL}>README on GitHub</a>
        </p>
      </footer>
    </div>
  );
}
