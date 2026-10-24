# Nexus911 screens: landing, sign in, onboarding, console header

This file adapts `design/nexus911-mock.html` to this repo. Layout, CSS classes and interaction follow the mock and `.kiro/steering/style-guide.md`. The words and behavior below replace the mock's v1 content (autonomous voice agents, Gemini, the competitor table, national call statistics, the highway-accident callers). Where this file and README.md disagree on behavior or data, README.md wins.

No backend changes are needed. Everything here uses existing endpoints: `GET /api/metrics`, `POST /api/reset` and `POST /api/simulation/start`.

## Flow and routes

**Landing → Sign in (or guest) → Onboarding → Console**

| Route | Screen | Guard |
|---|---|---|
| `/` | Landing | Always shown. CTAs read "Open the console" when a session exists, else "Get started" |
| `/signin` | Sign in (name only) with Continue as guest | With a session → `/operator` |
| `/welcome` | Onboarding, first visit per person | No session → `/signin` |
| `/operator` (default console), `/officer`, `/sim` | Console pages | No session → `/signin`. Not onboarded → `/welcome` |
| `*` | | → `/` |

## Storage

Every read and write is wrapped in try/catch, and the app still works when storage throws (onboarding simply shows each visit).

| Key | Store | Value |
|---|---|---|
| `nexus911:session` | localStorage | `{"kind":"guest"}` or `{"kind":"local","name":"…"}` |
| `nexus911:onboarded` | localStorage | `"1"`. The key is `nexus911:onboarded` for guests and `nexus911:onboarded:<name, lowercased>` otherwise |
| `nexus911:onboarding-step` | sessionStorage | Current step id, so a refresh returns to the same step |

`frontend/src/auth/session.ts` exports: the `Session` type; `getSession()`, `setSession(s)`, `clearSession()`; `onboardedKey(s)`, `isOnboarded(s)`, `markOnboarded(s)`, `clearOnboarded(s)`; `displayName(s)` (the name, or "Guest"); and a `useSession()` hook that re-reads on the `storage` event so two tabs stay in step.

## Landing (`/`)

Order: masthead → hero → problem → how it works → novelties → pull quote → Massachusetts table → limitations → get started → colophon. Every section is visible without JavaScript, and none waits at opacity 0 for an observer. One column at 860px and below; no sideways scroll at 390px.

**1. Masthead.** Wordmark · section nav (Problem · How it works · Novelties · Massachusetts · Limitations) · **Sign in** (ghost) · **Get started** (primary).

**2. Hero** (the disc sits behind the headline)
- Spec: `Claim-weighted 911` · `Prototype`
- Headline: Every call heard. *New facts* first.
- Lede: When many people call about one emergency, Nexus911 links the duplicates into one incident, weighs conflicting accounts by their evidence, and moves the call with new information to the top. Operators confirm or split every link.
- CTAs: **Run the demo →** (primary; to `/signin`, or `/welcome` with a session) · **How it works** (ghost; anchor link)
- Meta strip (mono): Quote-grounded claims · Three-band linking · Information-gain priority · Massachusetts-aware

**3. Problem**
- Spec: `The problem`
- Heading: Big incidents arrive as many small, separate calls.
- Stat block (the first stat gets the crimson top rule):
  - **10th**: A new emergency nearby can wait in the same queue as the tenth call about the last one.
  - **7 vs 3**: Callers disagree about what they saw, and a raw count can't say whose account to trust.
  - **Exit 8 = 63**: MassDOT renumbered highway exits, and callers on the Pike still use both numbers.
- Risk paragraph: Language models can help sort calls, but they can also *invent details*. Nexus911 keeps a fact only when it cites the caller's own words.

**4. How it works**
- Spec: `How it works` · `Seven steps, every call`
- Heading: From many calls to one incident.
- Numbered flow (seven items; at 980px and below, wrap to rows, and to one column at 560px):
  1. **Extract.** Claude turns the call into claims, each citing the caller's words.
  2. **Verify.** A claim whose quote isn't in the transcript is rejected.
  3. **Locate.** Massachusetts streets, towns, landmarks and old or new exit numbers.
  4. **Link.** Place, time, type and details give a match score: auto, suggest or new.
  5. **Weigh.** Reliability, recency and independence decide each value's share.
  6. **Prioritize.** New information rises. Repeats sink, but stay in the queue.
  7. **Dispatch.** One package with confidence and sources on every field.
- Results strip (mono, under the flow): On the three demo scenarios: 28 calls → 5 incidents · 5 of 5 new incidents surfaced · 10 of 10 new-information calls flagged · synthetic data

**5. Novelties**
- Spec: `What's new` · `Six ideas`
- Heading: Built to sort the calls, and to show its work.
- Six items (icon on a brand-tint tile, title, one line, mono tagline):
  - **Claim-level knowledge graph.** Every statement is its own node with its caller, quote and weight, so conflicting accounts are kept and weighed. *Claims, not records*
  - **Quote-grounded guard.** An AI-extracted fact must cite the transcript word for word, or it's rejected. *Hallucination check*
  - **Information-gain priority.** Repeats sink, new facts rise, and a new weapon, injury, location or hazard always escalates. *Severity × novelty*
  - **Independence-aware weighting.** Hearsay and repeat callers count for less, so an echoed rumor can't outvote eyewitnesses. *7–3 becomes 83–17*
  - **Explainable linking.** Auto-link, suggest or new, with every score component visible and one-click confirm or split. *Three bands*
  - **Massachusetts-aware.** Town ambiguity, old and new exit numbers, MBTA, campus and State Police routing, transfers, many languages. *Built for MA*

**6. Insight band** (card ground, 2px brand-rule top)
- Pull quote: No call is ever *dropped*. Nexus911 reorders and annotates the queue; it never hides a call.
- Caption: The principle behind Nexus911

**7. Massachusetts table**
- Spec: `Built for Massachusetts`
- Heading: Local problems, handled on purpose.
- A real `<table>` in an `overflow-x: auto` container, with three columns: Problem · How Nexus911 handles it (header underlined in crimson) · Demo. Use the seven rows from README "Massachusetts specifics" as written.

**8. Known limitations**
- Spec: `Known limitations`
- Heading: What this prototype can't do yet.
- Items (`!` marker in warn):
  - **Synthetic calls only.** No real 911, CAD, NG911 or speech recognition integration.
  - **Heuristic weights.** Thresholds and role priors haven't been validated with dispatch professionals.
  - **Simplified subjects.** Calls are aligned to one primary suspect and one vehicle.
  - **Demo map data.** Small Massachusetts samples with approximate coordinates.
  - **Illustrative units.** Recommended units aren't real dispatch protocols.
  - **Memory only.** State resets on restart, and latency isn't benchmarked.

**9. Get started**
- Heading: How would you like to start?
- Three choice cards:
  - **Continue as guest** (tag *Fastest*, recommended style): Use every feature right away. Nothing to fill in. · Continue →
  - **Sign in with your name**: We'll greet you by name and remember your intro in this browser. · Sign in →
  - **Read how it works first**: The seven-step pipeline, from first call to dispatch. · How it works ↑

**10. Colophon.** Wordmark · • Emergency dispatching, simplified • · Built for `<hackathon>` · MIT licence · Synthetic data only · a link to the README on GitHub.

## Sign in (`/signin`)

Split screen: the story panel on the left (card ground, with the disc cropped into its corner) and the form on the right. At 860px and below, the story panel collapses to a header strip and its proof list is hidden.

**Story panel**
- Wordmark
- Heading: Many calls. One *verified* incident.
- Proof list (crimson icons):
  - **Claims cite the caller.** Every fact shows its confidence and sources.
  - **New information rises.** A new weapon, injury or hazard goes to the top.
  - **You decide.** Confirm or split any link, and every decision is logged.
- Link: ← Nexus911 home

**Form**
- Spec: `Sign in` · `Prototype`
- Heading: Who's on the console?
- Lede: Tell us your name so we can greet you, or continue as a guest. Both get every feature.
- Field **Your name**: `autocomplete="name"`, required, 1–40 characters after trimming, letters, spaces, apostrophes and hyphens only.
  - Empty: "Enter your name, or continue as a guest."
  - Invalid: "Use letters, spaces, apostrophes or hyphens only."
  - On an error, focus returns to the field.
- Primary: **Continue →**. Then an "or" divider, then a full-width ghost **Continue as guest** with the line "Guests can use every feature."
- Note: "Your name is kept in this browser only. There's no password, because this prototype has no accounts."
- On success: `setSession`, then go to `/welcome`, or to `/operator` if that person has already finished onboarding.
- No password field, no tabs, no "forgot password".

## Onboarding (`/welcome`)

The BizzNex wizard pattern, exactly as in the mock: a fixed full-screen dialog (`role="dialog"`, `aria-modal="true"`), a 280px rail on card ground, a 2px crimson progress bar, the bloom, and a footer with **Back** · **Skip intro** · **Continue →**. The step is mirrored in sessionStorage. Focus moves to each step's `<h1>` (`tabIndex={-1}`), Tab stays inside the dialog, Escape skips, and the step 3 cards are a radiogroup with arrow-key navigation (roving tabindex). The rail is hidden at 860px and below, and the cards stack at 520px. Under reduced motion there is no step animation, fade or progress transition. Back is hidden on step 1.

**Rail:** Wordmark · 01 What it does · 02 How to read it · 03 Choose how to start · 04 Console · caption "About a minute. You can replay this from the console."

### Step 1 · What it does
- Spec: `STEP 1 OF 3` · `WHAT IT DOES`
- Heading: Many calls. One incident.
- Lede: "Welcome, {name}." (guests: "Welcome to Nexus911.") When many people call about the same emergency, Nexus911 links their calls into one incident, weighs what they say, and puts the calls with new information first.
- Points:
  - **Calls link into incidents.** Place, time, type and details give each link a score. Strong matches link on their own; weaker ones wait for you.
  - **New information rises.** A new weapon, injury, location or hazard goes to the top. Repeats sink, but no call ever leaves the queue.
  - **You stay in control.** Confirm or split any link. Every decision is logged.

### Step 2 · How to read it
- Spec: `STEP 2 OF 3` · `HOW TO READ IT`
- Heading: Every fact shows its evidence.
- Lede: Each detail lists every value callers reported, with its weighted share and the number of callers behind it. When callers disagree, it's flagged for you to decide.
- Points, using the real console components for the examples:
  - **Share and sources.** Example from the robbery demo: jacket white 83% · 7 sources, black 17% · 3 sources. Raw counts would say 70–30; hearsay and a repeat caller count for less.
  - **Contested.** The top value has under 70% and the runner-up at least 20%, like the SUV's color in the Pike crash (silver or white). Show the △ badge and text, with no made-up percentages.
  - **NEW INFO.** Why a call jumped the queue, in words: new weapon, new injury, new location, new hazard.
  - **Bands.** AUTO linked on its own · SUGGEST waits for you · NEW started an incident · CONFIRMED approved by an operator.
- Prototype notice (warn box): "This is a prototype. Every call is synthetic, and no real emergency services are contacted."

### Step 3 · Choose how to start
- Spec: `STEP 3 OF 3` · `CHOOSE HOW TO START`
- Heading: How would you like to start?
- Lede: Watch an incident come together, or go straight to the console.
- On entry, call `GET /api/metrics` with a 4-second timeout to check that the server is reachable.
- Cards (radiogroup):
  - **Run the Mass Ave robbery demo** · tag *Recommended* · "Eleven calls about one robbery, then a fire a block away. Watch duplicates sink and the new emergency jump to the top." Speed as a segmented control: 5× · 10× (default) · 20×. Caption: "This clears the console, then replays the calls."
  - **Open the operator console** · "Go straight to the queue. You can run any scenario from Sim."
- Server line:
  - Reachable: green dot, "Server reachable".
  - Unreachable (`role="alert"`, warn dot): "Can't reach the Nexus911 server, so the demo can't start. You can still open the console, or try again." with **Try again**. The demo card is disabled and the console card is selected.
- Primary button: **Run the demo →** or **Open the console →**, matching the choice.
  - Demo: `POST /api/reset`, then `POST /api/simulation/start` with `{"scenario_id": "mass_ave_robbery", "speed": <chosen>}`. While waiting, the button shows a spinner and "Starting the demo…". If the response says a replay is already running, treat it as success. On failure, show an inline `role="alert"` message with **Open the console instead**.
- Finish (any path, including Skip and Escape): `markOnboarded(session)`, clear `nexus911:onboarding-step`, go to `/operator`.

## Console header (every console page)

The existing top bar keeps its nav, connection dot and T+ clock, and gains:
- the Wordmark at the left;
- a "who" chip in mono: "Signed in as Dennis" or "Browsing as Guest";
- **Replay intro** (quiet): clears this person's onboarded flag and goes to `/welcome`;
- **Sign out** (quiet): clears the session and goes to `/`.
