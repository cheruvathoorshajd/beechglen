# PORT_PLAN: BizzNex typography + onboarding → Nexus911

Phase 1 audit (read only). Source: `../BizzNex` at `1fa102e`. Target: the Nexus911 repo at `9ca043c` (branch `bizznex-onboarding`).

> **Read with `FRONTEND_BUILD_PROMPT.md`.** This audit came first. Since then two things changed, and the build prompt wins wherever they differ:
> - **Colours:** the frontend uses the Nexus911 logo palette (black, crimson `#C00000`, white), not Nexus911's cyan theme. The colour table in §2 and decision D7 are superseded; see the prompt's **Palette** section and `STYLE_GUIDE.html`.
> - **Flow and sign-in:** §00 applies, and sign-in is mode B (name only, kept in the browser) unless the prompt's `SIGN_IN_MODE` says otherwise.

---

## 00. Revised flow (user request, supersedes D1)

**Landing → Sign in (with guest) → Onboarding → Product.** This is BizzNex's own flow (`views/Landing.tsx` → `views/Auth.tsx` → `onboarding/SetupWizard.tsx` → workspace; see `../BizzNex/docs/onboarding-flow.md`), so all three screens port from the same source pattern.

| # | Route | Screen | Source pattern | Nexus911 content |
|---|---|---|---|---|
| 1 | `/` | **Landing**: replaces the current `LandingPage.tsx` | BizzNex `Landing.tsx` + `landing.scss`: masthead with section nav and Sign in / Get started; serif hero with a lede and two CTAs; meta strip; a stat block; feature groups; a full-width insight band (pull quote); "How it works" flow; a closing "How would you like to start?" choice; colophon | From README.md, wording tightened: **Problem** (240M calls a year, 25–30% of dispatcher posts vacant, fragments across separate calls, LLMs hallucinate addresses); **Novelties**: the five capabilities plus the text fallback (agent per caller, role-aware conversation, cross-call intel sharing, VerifyLayer, deduplication, fallback); **What makes it different** (handles the call directly, not a dispatcher sidebar) with the competitive table; **How it works** (call → agent → knowledge graph → VerifyLayer → one incident → dispatch); **Known limitations** stated plainly (prototype, simulated callers, English only, in-memory state) |
| 2 | `/signin` | **Sign in**, with **Continue as guest** | BizzNex `Auth.tsx`: split screen with the story on the left and the form on the right; tabs Create account / Sign in; field validation, show/hide password, Caps Lock warning; **Explore the demo workspace** button → guest | Guest gets **every feature** (there is nothing to gate: the backend has no per-user data). See **A1** below for what "sign in" can mean |
| 3 | `/welcome` | **Onboarding wizard** | `SetupWizard.tsx` (§2) | Steps 1–3 in §3; first visit only, per user (or per browser for guests) |
| 4 | `/dashboard` | **Product**: the existing `DashboardPage`, behaviour unchanged | n/a | Header gains the signed-in name or "Guest", **Replay intro**, **Sign out** |

**Routing guard** (all in `main.tsx` + a small `session` module, no backend calls):
- `/dashboard` or `/welcome` without a session → `/signin`.
- Session present, `nexus911:onboarded` not set → `/welcome`, which then goes to `/dashboard`.
- `/signin` with a session → `/dashboard`.
- The landing page shows on every visit to `/`, like BizzNex. Its CTAs go to `/signin`, or to `/dashboard` when a session exists.

### A1. Sign-in: Nexus911 has no authentication

There is no user model, no auth route and no token anywhere in `api/`, `core/` or `agents/`, and the brief says the backend stays unchanged. So a real sign-in isn't possible without breaking that rule. Options:

| Option | What it is | Honest about | Cost |
|---|---|---|---|
| **(a) Guest-first, sign-in shown as "coming soon"** | The form is visible but disabled, with the note "Accounts aren't available in this prototype. Continue as guest to use everything." | Fully honest | Smallest. Sign-in is decoration |
| **(b) Local profile** | "Sign in" just asks for a name (and optionally role/agency), stored in `localStorage` under `nexus911:session`. No password, labelled "This prototype keeps your name in this browser only." | Honest, if it's labelled as not being real auth | Small. Gives onboarding a name to greet ("Welcome, Dennis") |
| **(c) Real auth** | Add users, password hashing, JWT and auth routes to the FastAPI backend | Real | **Breaks the "don't change the backend" rule**, plus storage (state is in memory today) |

What I won't do: a password form that accepts anything and pretends to authenticate. That looks like security without being any.

**Recommendation: (b)**, with the tabs reduced to one "Your name" form plus the guest button.

### Landing: what changes

- The current `LandingPage.tsx` (624 lines, Tailwind classes, Space Grotesk, cyan glows, `text-gradient`) is **rewritten** in the BizzNex landing pattern and fonts. Its content (README sections) carries over; its layout and glow effects don't.
- New CSS lives in `frontend/src/landing/landing.css`; the component moves to `frontend/src/landing/Landing.tsx`.
- The existing `navigate("/dashboard")` CTA becomes `navigate("/signin")`.

---

## 0. Decisions needed before Phase 2

| # | Finding | Recommendation |
|---|---|---|
| D1 | *(Superseded by §00: onboarding now has its own `/welcome` route between sign-in and the dashboard.)* **The live dashboard isn't `App`.** `main.tsx` routes `/` → `LandingPage` and `/dashboard` → `DashboardPage` (exported from `App.tsx`). The default export `App` (hero + dashboard) is never mounted. So "mount ahead of the dashboard in App.tsx" means wrapping **`DashboardPage`**. | Gate `DashboardPage`: the onboarding shows the first time someone reaches `/dashboard` (the landing CTA navigates there). The landing page stays as it is. Alternative: show it on `/` before the landing page. |
| D2 | **Simulation "voice" mode doesn't use the microphone.** In `POST /api/simulation/start` with `mode: "voice"`, Gemini Live voices the *simulated* callers and the browser only **plays** audio. The mic is used only by `VoiceCallPanel` (`/ws/voice`, `getUserMedia`), where the user talks as a caller. Voice also needs `GOOGLE_API_KEY` on the server, which falls back to text automatically when voice fails for every caller (`orchestrator.py:219`). | Step 3 offers **Run the highway demo** (text by default, voice as a toggle) and **Open the dashboard**. The mic is requested only if a third choice, **Call in yourself**, is picked, and only on that click. Confirm whether you want that third choice. |
| D3 | **Voice audio lives inside `SimulateModal`.** It owns the `/ws/simulation` socket and the per-caller `AudioContext`. If the onboarding starts a **voice** run and then lands on the dashboard, nothing plays the audio. A **text** run shows fully on the dashboard through `/ws/dashboard`. | Onboarding starts **text** mode directly. For voice, land on the dashboard with `SimulateModal` open, the highway scenario preselected, and the run started from there. That needs two optional props on `Dashboard`/`SimulateModal` (`initialOpen`, `autoStart`), both off by default, so current behaviour doesn't change. |
| D4 | **"Text simulation fallback when the backend is unreachable" isn't possible.** The text fallback runs **on the server** (`simulation/text_fallback.py`). With no backend there's nothing to simulate. | Unreachable (the `GET /api/simulation/scenarios` fetch fails or times out after 4 s): step 3 says so plainly and offers **Open the dashboard** (which shows its own disconnected state) and **Try again**. Reachable but voice unavailable: offer text mode. |
| D5 | **`npm run lint` doesn't exist.** `frontend/eslint.config.js` imports `@eslint/js`, `globals`, `typescript-eslint`, `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh`, but none are installed and `package.json` has no `lint` script. | Add `"lint": "eslint ."` and those 6 dev dependencies (the standard Vite template set). Pre-existing lint errors in `App.tsx`/`LandingPage.tsx` get **reported**, not fixed, unless the restyle caused them. Or skip lint. |
| D6 | **Weight mismatch.** Nexus911 headings use `font-bold` (700) and `font-black` (900) in Space Grotesk/Inter. BizzNex sets headings in **Fraunces 500** and never uses 700+ on the serif. | Either (a) load Fraunces as a variable font (one file covers 100–900, so Nexus911's weights render as real weights, not faux bold), or (b) also bring BizzNex's 500 headings over (a visual change to the dashboard). Recommend **(a)** with the exact BizzNex weights for the onboarding. |
| D7 | *(Resolved: the logo palette was chosen for this frontend; see the note at the top.)* **Brand clash (outside this repo).** The Nexus911 logo you showed earlier (`Nexus911.png` in this folder: crimson, high-contrast serif, heavy "911") is the planned brand for beechglen. This port puts BizzNex's Fraunces / Plex / Outfit into Nexus911. | Fine for this branch. If Nexus911 should end up on the logo's brand, the fonts here are throwaway. Say so now if that matters. |

---

## 1. Font table (source: BizzNex)

**Loading in BizzNex:** one Google Fonts `<link>` in `apps/web/index.html` with `display=swap` and `preconnect` to both hosts. Tokens are on `:root` in `styles/aurora.scss`. No `next/font`, no `@font-face`, no `@fontsource`, no Tailwind (BizzNex is plain SCSS).

| Token | Family | Requested from Google | Actually used (rule-by-rule scan of all `.scss` + inline `style`) | Where |
|---|---|---|---|---|
| `--serif` | **Fraunces** (variable, `opsz 9..144`) | 400, 500, 600; italic 500, 600 | **500** (17 rules), **400 italic** (2: `.pullquote`, landing blockquote), **500 italic** (landing hero `em`). 600 and italic 600 are **requested but unused**. 400 italic is **used but not requested** (the browser fakes it from the variable axis) | Headlines: `.view-title`, `.sec-t`, `.ob-h`, `.fi-t`, pull quotes |
| `--sans` | **IBM Plex Sans** | 400, 500, 600, 700 | **400** (body), **500** (`.btn`, emphasis), **600** (`<b>` in lists, card titles, user name); **700** only through browser-default `<b>`/`<strong>` | Body, buttons, inputs, card titles |
| `--mono` | **IBM Plex Mono** | 400, 500 | **400** (71 rules), **500** (`.spec`) | Labels, step counters, numbers (`.num` = tabular-nums), captions, nav groups, `kbd` |
| `--brand` | **Outfit** | 500, 700 | **700** (`.logo-name`), **500** (`.logo-tag`) | Logo wordmark only |

Fallback stacks: serif `Georgia, serif`; sans `system-ui, -apple-system, sans-serif`; mono `ui-monospace, monospace`; brand `'Avenir Next', 'Segoe UI', system-ui, sans-serif`.

### Type scale (BizzNex)

| Role | Font | Size | Line-height | Letter-spacing | Weight | Case |
|---|---|---|---|---|---|---|
| Body | sans | 15px | 1.6 | −0.006em | 400 | Sentence |
| Onboarding heading `.ob-h` | serif | clamp(2.1rem, 4.6vw, 3.4rem) | 1.02 | −0.035em | 500 | Sentence, max 20ch |
| Page title `.view-title` | serif | clamp(2rem, 4vw, 3rem) | 1 | −0.03em | 500 | Sentence |
| Section title `.sec-t` | serif | clamp(1.6rem, 3vw, 2.3rem) | n/a | −0.02em | 500 | Sentence |
| Onboarding lede `.ob-lede` | sans | 16.5px | 1.6 | n/a | 400 | max 56ch |
| Button `.btn` | sans | 14px (sm 13px) | n/a | −0.01em | 500 | Sentence |
| Card title `.ob-card-t` | sans | 15px | n/a | −0.01em | 600 | Sentence |
| Card body `.ob-card-b` | sans | 13.5px | 1.5 | n/a | 400 | |
| Spec line `.spec` ("STEP 2 OF 6") | mono | 11.5px | n/a | 0.2em | 500 | UPPER |
| Field label / `.ob-label` | mono | 11px | n/a | 0.1em | 400 | UPPER |
| Caption `.cap` | mono | 11px | n/a | 0.04em | 400 | Sentence |
| Step number `.ob-steps .n` | mono (`.num`) | 10.5px | n/a | −0.02em | 400 | n/a |
| Logo | brand | 21px | 0.8 | −0.02em | 700 | n/a |

### Target loading (Vite, per the font rules)

- **Self-host woff2 files** in `frontend/public/fonts/` with `@font-face` in `index.css`, latin subset, `font-display: swap`. I'm recommending this over `@fontsource` because the body weight has to be **preloaded**, and a fixed `/fonts/…` URL can go in `<link rel="preload">` in `index.html`. Fontsource emits hashed asset URLs that can't be preloaded without a plugin. The files come from the Fontsource/Google OFL builds, with each family's `OFL.txt` committed beside them.
- **Files** (exactly the used set, plus D6):

| File | Covers |
|---|---|
| `Fraunces-Variable.woff2` (wght + opsz) | 400–900 roman |
| `Fraunces-Italic-Variable.woff2` | 400, 500 italic (the italic BizzNex really uses) |
| `IBMPlexSans-400/500/600/700.woff2` | 4 static files (700 because of `<b>` and Nexus911's `font-bold`) |
| `IBMPlexMono-400/500.woff2` | 2 static files |
| `Outfit-500/700.woff2` | 2 files, used only if a wordmark is ported (see §3); otherwise dropped |

- **Preload:** `IBMPlexSans-400.woff2` (`<link rel="preload" as="font" type="font/woff2" crossorigin>`).
- **Remove** the Google Fonts `<link>` and its two `preconnect`s (Inter, Space Grotesk, JetBrains Mono) from `frontend/index.html`.

### Variables and replacements in Nexus911

`frontend/src/index.css` `@theme` (Tailwind v4 reads these as `font-*` utilities):

```css
--font-serif: "Fraunces", Georgia, serif;
--font-sans:  "IBM Plex Sans", system-ui, -apple-system, sans-serif;
--font-mono:  "IBM Plex Mono", ui-monospace, monospace;
--font-brand: "Outfit", "Avenir Next", "Segoe UI", system-ui, sans-serif;
--font-display: var(--font-serif);   /* keeps existing `font-display` classes working */
--font-body:    var(--font-sans);    /* keeps `body { font-family: var(--font-body) }` working */
```

Every font declaration in the target, and what it becomes:

| Location | Today | After |
|---|---|---|
| `index.html:9–11` | Google Fonts link: Inter 400–900, Space Grotesk 400–700, JetBrains Mono 400–700 | Removed; preload Plex Sans 400 |
| `index.css` `@theme --font-display` | Space Grotesk | `var(--font-serif)` |
| `index.css` `@theme --font-body` | Inter | `var(--font-sans)` |
| `index.css` `@theme --font-mono` | JetBrains Mono | IBM Plex Mono |
| `index.css:51` `body { font-family }` | `var(--font-body)` | unchanged (now Plex Sans) |
| `index.css:209–210` `.font-display`, `.font-mono` | vars | unchanged (now resolve to new families) |
| `App.tsx` 2× `font-display`, 16× `font-mono` | classes | unchanged; they pick up the new vars |
| `LandingPage.tsx` 16× `font-display`, 9× `font-mono` | classes | unchanged |
| `App.tsx` 4×, `LandingPage.tsx` 1× `italic` | sans italic (not loaded today either) | Flag: Plex Sans italic isn't in the BizzNex set, so the browser fakes it. Add `IBMPlexSans-Italic-400.woff2` or accept the faux italic |

No inline `fontFamily` styles exist in the target. The `font-family` grep finds only `index.css:51`, plus the two utility classes and the HTML link.

---

## 2. Onboarding anatomy (source: BizzNex)

BizzNex has five onboarding surfaces. **Only the Setup wizard is the pattern to port.** The others depend on accounts, records or a sidebar that Nexus911 doesn't have.

| Surface | File | Port? |
|---|---|---|
| **Setup wizard** (full-screen, step rail) | `onboarding/SetupWizard.tsx` + `styles/onboarding.scss` §"Setup wizard" | **Yes: this is the pattern** |
| Product tour (spotlight + coach card) | `onboarding/Tour.tsx` | No. Optional later (it could point at the incident list, the confidence bars and the Simulate button) |
| Getting-started checklist | `onboarding/Checklist.tsx`, `useChecklist()` | No: counts the user's CRM records |
| First-visit page intro | `onboarding/FeatureIntro.tsx` | No |
| Help (?) menu | `onboarding/HelpMenu.tsx` | Only its "Run setup again" item, as the **Replay intro** link |

### Setup wizard: how it works

| Aspect | BizzNex behaviour | Nexus911 port |
|---|---|---|
| **Layout** | `position: fixed; inset: 0; z-index: 120`. Two-column grid: a **280px rail** (logo, numbered step list, "About two minutes" caption) and a **main column** (body + sticky footer). A 2px **progress bar** runs along the top. A soft accent **bloom** (blurred radial glow) sits bottom-right. | Same grid, rail and progress bar. Bloom kept, tinted with Nexus911 cyan at low opacity (it matches the existing `animate-gradient-blob` look). |
| **Step model** | `type StepId` union + `FLOW: StepId[]` array + `LABELS` record. One `useState(step)` index; `id = flow[step]`; each step's JSX rendered under `{id === '…' && …}` in one component. Demo uses a shorter `DEMO_FLOW`. | `StepId = 'what' \| 'read' \| 'start'`, `FLOW` of 3. Step 4 ("land on the dashboard") isn't a screen: it's the wizard closing. The rail lists 4 items, the last being "Dashboard". |
| **State** | Component state for the step and answers. The step index is mirrored into `sessionStorage` (`bizznex.setup-step.<userId>`) so a refresh returns to the same step, inside try/catch. Completion goes to the account (`PATCH /onboarding`) or, for the demo, Redux + browser storage. | Step mirrored in `sessionStorage` (`nexus911:onboarding-step`, try/catch). **Completion → `localStorage["nexus911:onboarded"] = "1"`** in try/catch, as the brief requires. No Redux (Nexus911 has none). |
| **Progress indicator** | (1) Top bar: `width = step / (steps − 1)`, `transition: width .5s var(--ease)`, `aria-hidden`. (2) Rail list: 26px circular numbers `01…06` in mono; current = accent ring + 4px tint halo; done = filled accent with a tick icon. (3) Spec line "STEP 2 OF 6 · YOUR BUSINESS" above the heading. | All three. |
| **Transitions** | `.ob` fades in (`fade .3s`). Each step body remounts via `key={step}` and runs `obIn .45s cubic-bezier(.22,1,.36,1)`: opacity 0 → 1, translateY 14px → 0. Rail numbers/colours transition .2–.25s. No exit animation. | Same, in CSS keyframes (no framer-motion inside the wizard, so it matches the source exactly). |
| **Reduced motion** | Global rule in `aurora.scss:531` removes animations and transitions; `motion.ts` `reducedMotion()` short-cuts JS animation. | `@media (prefers-reduced-motion: reduce)` on `.ob*` turns off `obIn`, `fade`, the progress transition and the bloom. |
| **Validation** | Only the business step validates (required industry). On Continue: compute errors, focus the first bad field `#ob-<field>`, stay. Errors clear as each field is fixed. | No form fields, so nothing to validate. Step 3's choice is a radiogroup with a default, so Continue is always valid. Errors only from network calls (D4). |
| **Back / next / skip** | Footer: **Back** (quiet, hidden on step 1 and the last step) · right side: **Skip setup** (step 1) or **Skip this step** (optional steps) · **Get started** / **Continue →** (primary) · last step: **Go to my workspace** (ghost) + **Take the tour →** (primary). `Enter` in a field moves to the next field, never skips the step. | **Back** · **Skip intro** on *every* step (brief) · **Continue →** / final **Run the demo →** or **Open the dashboard →**, whichever was chosen. |
| **Async step** | The data step awaits `seed()`; the primary button shows a spinner + "Adding sample data…" and is disabled; on failure an inline `role="alert"` error shows and the step stays. | Same for `POST /api/simulation/start`: spinner + "Starting the demo…". On failure, an inline alert with **Open the dashboard instead**. |
| **Focus / keyboard** | `role="dialog" aria-modal="true" aria-label`. On each step change, focus moves to the first `[data-autofocus]` element (the primary button or first card) with `preventScroll`. Option cards are `<button aria-pressed>` (multi) or `role="radio" aria-checked` inside `role="radiogroup"`. `:focus-visible` = 2px accent outline, 2px offset. The `?` shortcut is suppressed while `.ob` is open. No focus trap and no Escape handling in the wizard itself. | Brief changes one thing: **focus goes to the step's `<h1>`** (`tabIndex={-1}`), not the primary button. Plus: a focus trap inside the dialog (Tab cycles inside), **Escape = Skip**, and arrow keys inside the radiogroup (roving tabindex), which BizzNex lacks on its radio cards. `inert` on the dashboard behind it. |
| **Responsive** | ≤860px: one column, rail hidden (progress bar + spec line remain). ≤520px: 16px body padding, cards stack to one column, footer buttons tighten. | Same breakpoints. Verified at 390px in Phase 3. |
| **Completion** | `finish(tour)` clears the step key, saves `wizard: 'done'`, closes, then either starts the tour or navigates to the first goal's view. | `finish(choice)`: clear the step key, set `nexus911:onboarded`, close, render the dashboard; if the demo was chosen, it's already running (or per D3). |
| **Re-entry** | Help menu → "Run setup again" sets `wizard: 'pending'`. | **Replay intro** link in the dashboard header reopens the wizard without clearing the flag until it finishes again. |

### Dependencies the onboarding relies on

| Dependency | Used for | Port decision |
|---|---|---|
| Redux (`@reduxjs/toolkit`, `react-redux`) | Session, theme/language, demo progress | **Drop**: component state + storage |
| RTK Query `services/api` | `useMeQuery`, `PATCH /onboarding`, `seed` | **Drop**: one plain `fetch` for scenarios and one for start |
| `@bizznex/shared` | Types (`OnboardingState`, goals) | **Drop** |
| `@formkit/auto-animate` | List motion (checklist, not the wizard) | **Not needed** |
| `react-intl` / `i18n/useT` | Translations (not in the wizard) | **Not needed** |
| `ui/Icon.tsx` (custom inline SVG set) | Step ticks, point icons, arrow | **Rebuild with `lucide-react`**, already a Nexus911 dependency (`Check`, `ArrowRight`, `Users`, `ShieldCheck`, `Radio`, `LayoutDashboard`, `Mic`). Same 1.8 stroke. |
| `ui/Logo.tsx` (Outfit wordmark) | Rail logo | Rebuild as a plain "Nexus911" wordmark (see §3 colour note) |
| SCSS (`sass`) | Stylesheet | **Not added**: plain CSS in `onboarding/onboarding.css` (Tailwind v4 is already there, but the source pattern is class-based CSS, so plain CSS keeps it 1:1) |
| `framer-motion` | Not used by BizzNex | Already in Nexus911; **not used** by the port |

**New dependencies proposed: none for the onboarding.** For lint only (D5): `eslint`, `@eslint/js`, `globals`, `typescript-eslint`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`.

### Colours: BizzNex token → existing Nexus911 token

BizzNex is light + dark; Nexus911 is dark only, so the mapping uses the BizzNex **dark** values' roles.

| BizzNex | Role | Nexus911 | Contrast on `#0B0F19` | Note |
|---|---|---|---|---|
| `--paper` | page ground | `--color-surface-base` #0B0F19 | n/a | |
| `--paper-2` | rail ground | `--color-surface-card` #141824 | n/a | |
| `--paper-3` | raised | `--color-surface-elevated` #1C2133 | n/a | |
| `--ink` | text | body `#E1E1E1` | 14.6 ✓ | Hard-coded in `body`; no token. **Flag:** add `--color-ink` alias, or reference the literal |
| `--ink-soft` | lede | Tailwind `gray-400` | 7.4 ✓ | **Conflict:** no Nexus911 token; the dashboard uses Tailwind greys directly |
| `--muted` | labels, captions | Tailwind `gray-400` (not `gray-500`/`status-off`) | 7.4 ✓ | `gray-500` / `status-off` #6B7280 = **3.96, fails AA** for the 11px mono labels |
| `--rule` / `--rule-soft` | borders | `--color-border-default` / `--color-border-subtle` | n/a | |
| `--accent` | primary, current step, focus ring | `--color-accent-cyan` #22D3EE | 10.6 ✓ | **Conflict:** Nexus911 has three accents (blue/cyan/purple). Cyan chosen: it's the landing page's CTA/glow colour. Primary button text = surface-base on cyan (10.6 ✓) |
| `--accent-tint` | halos, icon tiles, selected card | cyan at 10–14% | n/a | |
| `--ok` / `--warn` / `--bad` | states | `--color-status-normal` / `-medium` / `-critical` | ✓ / ✓ / 5.1 ✓ | Used only for the reachability notice and errors |
| `--radius` 3px | corners | **Conflict:** Nexus911 uses `rounded-xl`/`rounded-2xl` glass cards | n/a | Keep BizzNex's 3px inside the onboarding (pattern fidelity) or match the dashboard's rounding. Recommend 3px |
| `.bloom` | background glow | existing `gradient-blob` style | n/a | |

---

## 3. Nexus911 step content

Copy follows the BizzNex pattern: spec line, serif heading (≤20ch), sans lede (≤56ch), then a hairline list or option cards.

**Rail:** `Nexus911` wordmark · `01 What it does` · `02 How to read it` · `03 Choose how to start` · `04 Dashboard` · caption: *About a minute. You can replay this from the dashboard.*

### Step 1 · What it does
- Spec: `STEP 1 OF 3 · WHAT IT DOES`
- Heading: **Three callers. One incident.**
- Lede: When several people call about the same emergency, Nexus911 gives each caller their own AI agent, cross-checks what they say, and merges it into one verified incident.
- Points (hairline list, icon + bold + line):
  - **Every caller gets an agent.** It asks what that caller can answer: a child, a witness and a driver each see something different.
  - **Accounts are cross-checked.** Details that match across callers gain confidence; details that conflict are caught.
  - **One incident, not three.** Duplicate calls merge into a single record with the dispatch recommendation.
- Footer: Skip intro · **Continue →**

### Step 2 · How to read it
- Spec: `STEP 2 OF 3 · HOW TO READ IT`
- Heading: **Every fact shows its evidence.**
- Lede: Each detail on an incident carries a confidence score and the number of callers who reported it. Where callers disagree, the detail is flagged for a person to decide.
- Points:
  - **Confidence**: a bar from 0 to 100%, rising as independent callers agree. (Use the dashboard's own `ConfidenceBar` look for the example.)
  - **Sources**: how many callers reported this detail.
  - **Disputed**: callers disagree, and a human decides.
- Notice (plain, not hidden in small print): **This is a prototype. The callers are simulated, and no real emergency services are contacted.**
- Footer: Back · Skip intro · **Continue →**

### Step 3 · Choose how to start
- Spec: `STEP 3 OF 3 · CHOOSE HOW TO START`
- Heading: **How would you like to start?**
- On entry: `GET /api/simulation/scenarios` (4 s timeout). Find `name === "highway_accident"` (title "Highway Multi-Vehicle Accident", 3 callers); if it's missing, use the first scenario whose `incident_type` is a traffic one, else the first scenario.
- Radiogroup cards (BizzNex `.ob-cards.two`):
  - **Run the highway accident demo** · tag *Recommended* · "Three simulated callers report a multi-vehicle crash: a child, a witness and a truck driver. Watch their accounts merge into one incident." Sub-option: `Text` (default) / `Voice` segmented control, with the note "Voice plays the callers' audio and needs a Gemini key on the server."
  - **Open the dashboard** · "Go straight to the live dashboard. You can start any simulation from Simulate."
  - (Optional, D2) **Call in yourself** · "Talk to the dispatcher agent as a caller. Your browser will ask for the microphone."
- States:
  - Loading scenarios: cards render; the demo card shows "Checking the server…" and is disabled until the fetch resolves.
  - Unreachable (D4): notice "Can't reach the Nexus911 server, so the demo can't start. You can still open the dashboard, or try again." The demo card is disabled; **Try again** re-fetches.
- Primary button: **Run the demo →** or **Open the dashboard →**. On demo: `POST /api/simulation/start {"scenario": "highway_accident", "mode": "text"|"voice"}`. The server returns 409-style detail if a simulation is already running: treat "already running" as success and land on the dashboard.

### Step 4 · Dashboard
Not a screen. The wizard closes, `nexus911:onboarded` is set, and the dashboard renders with the demo running if chosen (D3 for voice). The dashboard header gets a small **Replay intro** link, the only change to the dashboard's markup.

---

## 4. Files Phase 2 would touch

| File | Change |
|---|---|
| `frontend/public/fonts/*.woff2` + `OFL.txt` | New |
| `frontend/index.html` | Swap Google Fonts link for one preload |
| `frontend/src/index.css` | `@font-face` blocks; `@theme` font vars |
| `frontend/src/landing/` | New: `Landing.tsx`, `landing.css` (replaces `src/LandingPage.tsx`, which is removed) |
| `frontend/src/auth/` | New: `SignIn.tsx`, `session.ts` (localStorage `nexus911:session`, try/catch), `auth.css` |
| `frontend/src/main.tsx` | Routes `/`, `/signin`, `/welcome`, `/dashboard` + guard |
| `frontend/src/onboarding/` | New: `Onboarding.tsx`, `steps.ts` (copy), `useOnboarded.ts` (storage), `onboarding.css` |
| `frontend/src/App.tsx` | `DashboardPage`: render `<Onboarding>` until onboarded; pass `onReplayIntro` to `Dashboard`; add the header link. D3 props if voice is approved. No changes to WebSocket, `useApi`, `SimulateModal` logic or `VoiceCallPanel` |
| `frontend/package.json` | Only if D5: `lint` script + ESLint dev deps |
| Backend, `api/`, `simulation/`, `tests/` | **No changes** |

Commits (Phase 3, local only): fonts → onboarding component → App.tsx wiring → fixes.
