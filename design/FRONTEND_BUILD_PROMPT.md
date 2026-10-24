# Build prompt: Nexus911 frontend (landing → sign in → onboarding → product)

**Setup:** copy this whole design folder into the Nexus911 repo as `design/` (so the repo has `design/Nexus911.png`,
`design/PORT_PLAN.md`, `design/nexus911-mock.html` and `design/STYLE_GUIDE.html`), and clone BizzNex beside the repo
as `../BizzNex`. Then paste everything below the line into a Claude Code session started in the Nexus911 repo root.
Set the one option first.

```
SIGN_IN_MODE = B        # A = guest only · B = name only, local (chosen) · C = real accounts
```

---

## Context

Two repos sit side by side:
- **SOURCE:** `../BizzNex`, the reference for typography, the landing page, the sign-in screen and the onboarding wizard. Its frontend is `apps/web` (Vite + React + SCSS).
- **TARGET:** `./`, Nexus911. Its frontend is `frontend/` (React 19 + Vite 6 + TypeScript + Tailwind v4, with `framer-motion` and `lucide-react`). Its backend is FastAPI (`api/`, `core/`, `agents/`, `simulation/`, `verification/`).

Read `design/PORT_PLAN.md` first, and open `design/nexus911-mock.html` and `design/STYLE_GUIDE.html` in a browser. It holds the audit: the font table, the type scale, the onboarding anatomy, the colour mapping and the step copy. This prompt is the build order. Where they differ, this prompt wins.

**Goal:** four screens in this order. Behind them, the existing dashboard behaves exactly as it does today.

| Route | Screen |
|---|---|
| `/` | Landing: problem, novelties, what makes it different, how it works, limitations |
| `/signin` | Sign in (per `SIGN_IN_MODE`) with **Continue as guest**. Guests get every feature |
| `/welcome` | Onboarding wizard, first visit only |
| `/dashboard` | The existing `DashboardPage` from `frontend/src/App.tsx` |

## Rules

- **Never push, open a PR, or push branches or tags.** Commit locally only, in the steps listed at the end.
- **Don't change the backend, the API, the WebSocket logic or the dashboard's behaviour.** The only exception is `SIGN_IN_MODE = C`, which adds auth routes and nothing else.
- **Don't fake authentication.** No password field that accepts anything. If there's no real check, the UI says so.
- **No Anthropic or Claude API keys and no LLM calls from the frontend.**
- Port BizzNex's **patterns, structure, interaction and fonts**, not its business content, Redux store, RTK Query or backend calls.
- Plain React + CSS. Add no runtime dependency for the landing, sign-in or onboarding. Icons come from `lucide-react` (already installed).
- **Colours come from the Nexus911 logo (`design/Nexus911.png`), not from BizzNex and not from the current cyan theme.** Use only the tokens in the **Palette** section below. Don't import BizzNex's palette. This overrides the colour table in `design/PORT_PLAN.md` §2. The reasoning behind every colour, type and component choice is in `design/STYLE_GUIDE.html`.
- Every `localStorage` / `sessionStorage` read and write is wrapped in try/catch, and the app works when storage throws.
- Respect `prefers-reduced-motion` everywhere you add motion.

## Storage keys

| Key | Store | Value |
|---|---|---|
| `nexus911:session` | localStorage | `{"kind":"guest"}`, `{"kind":"local","name":"…"}` or `{"kind":"account","name":"…","email":"…"}` (C only; the token is never stored here) |
| `nexus911:onboarded` | localStorage | `"1"`, **scoped per person**: the key is `nexus911:onboarded` for guests, `nexus911:onboarded:<name or email, lowercased>` otherwise |
| `nexus911:onboarding-step` | sessionStorage | current step id, so a refresh returns to the same step |
| `nexus911:token` | sessionStorage | C only: the JWT |

## Palette (from the Nexus911 logo)

The colours were sampled from `design/Nexus911.png`: a pure black ground, one crimson (`#C00000` for the disc and "911", `#B40000` for the underline rules) and white type. The app is dark only.

| Token (`@theme`) | Value | Use |
|---|---|---|
| `--color-ground` | `#000000` | Page background |
| `--color-card` | `#0C0C0C` | Panels, story panel, onboarding rail |
| `--color-raised` | `#161616` | Raised rows, selected segments |
| `--color-ink` | `#FFFFFF` | Headings and body text |
| `--color-ink-soft` | `#A3A3A3` | Secondary text, labels, captions (8.3:1 on black) |
| `--color-rule` | `rgba(255,255,255,.14)` | Borders, inputs |
| `--color-rule-soft` | `rgba(255,255,255,.08)` | Hairline dividers |
| `--color-brand` | `#C00000` | **The only red.** Fills, icons, dots, large type |
| `--color-brand-rule` | `#B40000` | Underline rules (wordmark, emphasised words, band top) |
| `--color-brand-tint` | `rgba(192,0,0,.18)` | Focus halos, selected-card glow, icon tiles |
| `--color-ok` | `#22C55E` | Confirmed / high confidence |
| `--color-warn` | `#EAB308` | Caution / disputed |

**Contrast rules (WCAG AA):**
- Crimson on black is **3.24:1**. Use it as **text only at 24px+, or 18.66px+ bold** (the wordmark "911", big stat numbers), and freely for non-text: icons, dots, rules, borders, focus rings (the 3:1 minimum).
- **Never small crimson text on black.** Every label, link, tag or caption that would have been accent-coloured is **white**, with crimson carried by a dot, rule or underline beside it (e.g. `.spec .k` gets a 6px crimson dot before it).
- Crimson **fills** take **white text** (6.48:1): primary buttons, the "Recommended" tag, finished-step circles, the Critical badge.
- **Critical severity uses the brand crimson.** There is no second red. Critical always also carries the word "Critical" and the 3px left stripe, so it's never shown by colour alone.
- No cyan, blue or purple anywhere in new screens, and no gradient text.

**Logo motifs to reuse:**
- **Wordmark:** "NEXUS" in `--font-serif`, weight 400, uppercase, `letter-spacing: .16em`, white; then "911" in `--font-sans` 700, crimson; a 2px `--color-brand-rule` underline under the lockup. Build it as a `Wordmark` component used on every screen.
- **Disc:** a flat crimson circle (no blur, no gradient) behind the landing hero headline, offset right (`width: min(44vw, 470px)`, 230px on phones), and a smaller one cropped into the corner of the sign-in story panel. Text over it stays white (6.48:1). Keep grey text off the disc.
- **Underlines:** emphasised words in headlines are white italic with a crimson underline (`text-decoration-color: var(--color-brand-rule)`), not crimson text.
- **Bullets:** the logo's `•  EMERGENCY DISPATCHING, SIMPLIFIED  •` framing, used in the landing colophon.
- The onboarding keeps a soft crimson glow (`radial-gradient` of brand at 30%, blurred) rather than a flat disc, so its text stays readable.

---

## Step 1: Fonts

1. Download the **latin** woff2 files for exactly this set from the Fontsource/Google OFL builds into `frontend/public/fonts/`, each family's `OFL.txt` beside its files:
   - `Fraunces` variable (wght + opsz) roman, and variable italic
   - `IBM Plex Sans` 400, 500, 600, 700, and italic 400 (the dashboard uses `italic`)
   - `IBM Plex Mono` 400, 500
   - `Outfit` 500, 700 (wordmark only; drop them if no wordmark uses Outfit)
2. In `frontend/src/index.css`, add one `@font-face` per file with `font-display: swap` and the right `font-weight` / `font-style` (a range such as `100 900` for the variable files).
3. In the `@theme` block:
   ```css
   --font-serif: "Fraunces", Georgia, serif;
   --font-sans:  "IBM Plex Sans", system-ui, -apple-system, sans-serif;
   --font-mono:  "IBM Plex Mono", ui-monospace, monospace;
   --font-brand: "Outfit", "Avenir Next", "Segoe UI", system-ui, sans-serif;
   --font-display: var(--font-serif);
   --font-body:    var(--font-sans);
   ```
4. In `frontend/index.html`, remove the Google Fonts `<link>` and both `preconnect` tags. Add `<link rel="preload" href="/fonts/IBMPlexSans-400.woff2" as="font" type="font/woff2" crossorigin>`.
5. Grep `frontend/` for `font-family`, `fontFamily`, `Inter`, `Space Grotesk` and `JetBrains`. Nothing may remain outside the theme layer.

Commit: `fonts: self-host BizzNex type families and expose them as theme variables`.

## Step 1b: Colours

1. Add the **Palette** tokens to `@theme` in `frontend/src/index.css`.
2. Re-point the existing tokens so the dashboard follows without logic changes:
   - `--color-surface-base` → ground, `-card` → card, `-elevated` → raised, `-hover` → `#1F1F1F`;
   - `--color-border-*` → the rule values;
   - `--color-accent-blue`, `--color-accent-cyan` and `--color-accent-purple` → brand;
   - `--color-status-critical` → brand, `-high` → `#F97316` (unchanged), `-medium` → warn, `-normal` → ok, `-standby` → ink-soft, `-off` → `#6B6B6B`.
   - `body { color }` → `var(--color-ink)`. `<meta name="theme-color">` in `index.html` → `#000000`.
3. Grep `frontend/src` for hard-coded colours: `#`-hex, `rgb(`, `rgba(`, and Tailwind colour utilities (`text-|bg-|border-|from-|to-|via-|ring-|shadow-` followed by `blue|cyan|sky|indigo|purple|violet|teal`). For each one in `App.tsx` and `index.css`:
   - an accent used as **small text** → `text-white` (or ink), with the crimson moved to an adjacent dot or border;
   - an accent used as a **fill, border, icon or large number** → the brand token;
   - **glows and gradients** (`.glow-cyan*`, `.text-gradient*`, cyan `box-shadow`s, `.stat-card::after`, `.pipeline-connector::after`, `.glass-highlight::before`) → remove the colour effect, or replace it with a flat brand rule.
   
   Class names and markup structure stay the same; only colour values change. List every replacement in the final report.
4. Check contrast for every text/background pair you touched against the rules above, and list any pair under 4.5:1 (body) or 3:1 (large text, UI).

Commit: `colours: retheme to the Nexus911 logo palette (black, crimson, white)`.

## Step 2: Session module

Create `frontend/src/auth/session.ts`:
- `type Session = { kind: 'guest' } | { kind: 'local'; name: string } | { kind: 'account'; name: string; email: string }`
- `getSession(): Session | null`, `setSession(s)`, `clearSession()`, all try/catch, returning `null` on any failure or malformed JSON.
- `onboardedKey(s: Session)`, `isOnboarded(s)`, `markOnboarded(s)`, `clearOnboarded(s)` using the scoped key above.
- `displayName(s)`: the name, or `"Guest"`.
- A tiny `useSession()` hook that re-reads on the `storage` event, so two tabs stay in step.

## Step 3: Routing and guard

In `frontend/src/main.tsx`, routes `/`, `/signin`, `/welcome`, `/dashboard`, and `*` → `/`. Add a `RequireSession` wrapper:
- `/dashboard` and `/welcome` with no session → `<Navigate to="/signin" replace>`.
- `/dashboard` with a session that isn't onboarded → `/welcome`.
- `/signin` with a session → `/dashboard`.
- `/` always shows the landing page. Its CTAs read "Open the dashboard" when a session exists, else "Get started".

## Step 4: Landing page

Rewrite the landing page as `frontend/src/landing/Landing.tsx` + `landing.css`, following the **structure** of `../BizzNex/apps/web/src/views/Landing.tsx` and `styles/landing.scss`. Delete `frontend/src/LandingPage.tsx` once nothing imports it. Content comes from `README.md` in TARGET, rewritten in short plain sentences:

1. **Masthead:** Nexus911 wordmark · section nav (Problem · How it works · Novelties · Limitations) · **Sign in** · **Get started** (primary).
2. **Hero:** serif headline about many callers, one incident. A lede that names the job: autonomous AI agents take simultaneous 911 calls, share what they learn, and verify it before dispatch. Two CTAs: **Run the demo** (→ `/signin`) and **How it works** (anchor). Meta strip in mono: `3+ agents at once · VerifyLayer · Geo + time + semantic dedup · Text fallback`.
3. **Problem:** a stat block with `240M` calls a year in the US, `25–30%` of dispatcher posts vacant, and fragments spread across separate call records. One paragraph on LLM hallucination risk (a wrong address sends responders to the wrong place).
4. **How it works:** a numbered flow, which really is a sequence: caller → dedicated agent → shared knowledge graph → VerifyLayer → one incident → dispatch package.
5. **Novelties:** six items from README "Five Capabilities": an agent per caller, role-aware conversation, cross-call intel sharing, VerifyLayer, incident deduplication, text fallback. BizzNex feature-group layout; each item gets a mono tag line.
6. **Insight band:** a serif pull quote: the verification layer is what makes autonomous handling defensible.
7. **What makes it different:** the README competitive table as a real `<table>` in an `overflow-x: auto` container. Replace each ✅/❌/⚠️ with text plus a glyph ("Full", "No", "Partial") so colour isn't the only signal.
8. **Known limitations:** the README list, stated plainly: prototype, simulated callers, unmeasured latency, heuristic roles, English only, in-memory state.
9. **Get started:** BizzNex's "How would you like to start?" closing choice: **Continue as guest** · **Sign in** (plus **Create account** in mode C).
10. **Colophon:** repo name, licence, a link to `README.md` on GitHub.

Landing visuals: the `Wordmark` in the masthead and colophon; the flat crimson **disc** behind the hero headline; emphasised hero words white italic with a crimson underline; section `spec` labels with a crimson dot; the insight band with a 2px crimson top rule; competitor-table "Nexus911" column header underlined in crimson; feature icons crimson on a brand-tint tile.

Landing rules: keep the existing `useReveal` behaviour only if every section is visible without JavaScript. No section may sit at `opacity: 0` waiting for an observer. Single column at ≤860px. No horizontal scroll at 390px.

Commit: `landing: rebuild in the BizzNex landing pattern with Nexus911 content`.

## Step 5: Sign in

Build `frontend/src/auth/SignIn.tsx` + `auth.css` on the **BizzNex `views/Auth.tsx` split-screen pattern**: a story panel on the left (serif line, three short proof points, a link back to the landing page) and the form panel on the right. ≤860px: the story panel collapses to a header strip.

**Always present:** a full-width **Continue as guest** button with the line *"Guests can use every feature."* On click: `setSession({kind:'guest'})`, then go to `/welcome`, or `/dashboard` if already onboarded.

### Mode A: guest only

- Show the email/password form **disabled** (`disabled`, `aria-disabled`), with the notice *"Accounts aren't available in this prototype. Continue as guest to use everything."*
- The guest button is the primary action and gets focus on load.
- No other way in.

### Mode B: name only, local (chosen)

- One field: **Your name** (`autocomplete="name"`, required, 1–40 characters after trimming, letters, spaces, `'` and `-`). Inline error in the BizzNex `.field-err` style. On submit with an error, focus the field.
- Primary: **Continue →**. On submit: `setSession({kind:'local', name})`, then route as for guests.
- Under the form, plainly: *"Your name is kept in this browser only. There's no password, because this prototype has no accounts."*
- No tabs, no password field, no "forgot password".
- If a session for the same name was onboarded before, skip `/welcome`.

### Mode C: real accounts (backend change; only in this mode)

Backend, additive only, without touching existing routes, agents, simulation or verification:
- `api/auth_routes.py` with an `APIRouter(prefix="/api/auth")`, included in `api/main.py`:
  - `POST /register {name, email, password}` → 201 `{token, user}`. 409 if the email exists. 422 on validation.
  - `POST /login {email, password}` → 200 `{token, user}`. 401 with one generic message on a wrong email *or* password.
  - `GET /me` with `Authorization: Bearer` → `{user}`, or 401.
- Storage: SQLite via the standard library (`sqlite3`), file path from a new `AUTH_DB_PATH` setting in `core/config.py` (default `data/auth.db`, gitignored). Users table: id, name, email (unique, lowercased), password_hash, created_at.
- Hashing: `bcrypt` (add to `requirements.txt`). Never log or return the hash.
- Tokens: `PyJWT` (add to `requirements.txt`), HS256, 12-hour expiry, secret from a new `AUTH_JWT_SECRET` setting. **Refuse to start auth** (return 503 from the auth routes) if the secret is empty or the placeholder, and add it to `.env.example` with a note to set it.
- Rate-limit `/login` to 10 attempts per minute per IP, in memory.
- Tests in `tests/test_auth.py`: register, duplicate email, login success, wrong password, `/me` with valid, expired and missing tokens, and 503 without a secret. All existing tests must still pass.
- **Nothing else requires auth.** The dashboard, simulation and WebSocket routes stay open, so guests keep every feature.

Frontend:
- BizzNex tabs **Create account / Sign in** (`role="tablist"`). Fields with validation, show/hide password, a Caps Lock warning, and an inline `role="alert"` error for server errors.
- Store the token in `sessionStorage` (`nexus911:token`) and the session (without the token) in `localStorage`. On load, if a token exists, call `GET /api/auth/me`. On 401, clear both and keep the person on `/signin` with "Your session ended. Sign in again."
- If `/api/auth/*` returns 503 or the network fails, show *"Accounts are unavailable right now. You can continue as guest."* The guest button still works.

Commit: `auth: sign-in screen (mode <A|B|C>) with guest access`. In mode C, make a separate earlier commit for the backend: `api: add optional account routes`.

## Step 6: Onboarding wizard

Build `frontend/src/onboarding/` (`Onboarding.tsx`, `steps.ts`, `onboarding.css`) on the **BizzNex `onboarding/SetupWizard.tsx` pattern**, as documented in `design/PORT_PLAN.md` §2. That covers:
- the full-screen layout with a 280px step rail and the 2px top progress bar;
- the "STEP n OF 3 · …" spec line, a serif heading and a sans lede;
- the `obIn` step-entry animation (keyed remount);
- the footer with Back, Skip and Continue.

Copy is in `design/PORT_PLAN.md` §3. Greet by name in step 1 ("Welcome, Dennis.") for local and account sessions, and with no name for guests.

Behaviour:
- **Skip intro** on every step: marks onboarded and goes to `/dashboard`. **Escape** does the same.
- Back is hidden on step 1. Continue moves forward. The final button reads **Run the demo →** or **Open the dashboard →** to match the choice.
- On every step change, focus moves to the step's `<h1>` (`tabIndex={-1}`). The wizard is `role="dialog" aria-modal="true"`, traps Tab inside itself, and the step-3 cards are a `role="radiogroup"` with arrow-key navigation (roving tabindex).
- Step 3 calls `GET /api/simulation/scenarios` with a 4-second timeout. Pick `name === "highway_accident"`. If it's missing, pick the first scenario whose `incident_type` mentions a vehicle or traffic, else the first one.
  - **Run the highway accident demo**: segmented **Text** (default) / **Voice**. Text: `POST /api/simulation/start {"scenario":"highway_accident","mode":"text"}`, then go to `/dashboard`. Voice: go to `/dashboard?simulate=highway_accident` (see Step 7). The browser needs a user gesture for audio, and the Simulate window owns playback.
  - **Open the dashboard**.
  - If the start response says a simulation is already running, treat it as success.
  - Unreachable server (timeout or network error): the demo card is disabled. Show *"Can't reach the Nexus911 server, so the demo can't start. You can still open the dashboard, or try again."* with **Try again**.
  - **Never** call `getUserMedia` from the onboarding. The microphone is only requested by the dashboard's existing "call in" panel, when the user opens it.
- Completion: `markOnboarded(session)` and clear `nexus911:onboarding-step`.
- Responsive per BizzNex: the rail is hidden at ≤860px, and the body padding is 16px with single-column cards at ≤520px.

Commit: `onboarding: three-step intro in the BizzNex wizard pattern`.

## Step 7: Dashboard wiring (markup additions only)

In `frontend/src/App.tsx`:
- `DashboardPage` reads the session. The `Dashboard` header gets a small cluster: the display name (or "Guest"), **Replay intro** (clears this person's onboarded flag → `/welcome`) and **Sign out** (clears the session, and the token in mode C → `/`).
- Add two optional props, both off by default: `Dashboard({ initialSimulate?: string })` and `SimulateModal({ initialScenario?: string; autoStart?: boolean })`. When `/dashboard?simulate=<name>` is present, open `SimulateModal` with that scenario selected and `mode: "voice"`. **Don't** auto-start voice; the user presses Start, which supplies the gesture audio needs. Remove the query parameter after reading it.
- Change nothing in `useWebSocket`, `useApi`, `VoiceCallPanel`, the incident logic, or `SimulateModal`'s socket and audio code.
- Delete the unused default export `App` (hero + dashboard) only if nothing imports it. Otherwise leave it.

Commit: `app: route the dashboard behind sign-in and onboarding; add replay and sign-out`.

## Step 8: Lint setup

`frontend/eslint.config.js` exists, but its packages and the script don't. Add `"lint": "eslint ."` and the dev dependencies `eslint`, `@eslint/js`, `globals`, `typescript-eslint`, `eslint-plugin-react-hooks` and `eslint-plugin-react-refresh`, at versions compatible with the config's imports. Fix lint errors in files you created or changed. **List** pre-existing errors in untouched code without fixing them.

Commit: `chore: add the lint script the existing eslint config expects`.

## Step 9: Verify

1. In `frontend/`, run `npm install`, `npm run build` and `npm run lint`. From the root, run `python -m pytest tests/ -v`. Fix anything this work broke.
2. Start the backend (`python run.py`, port 8080) and the frontend (`npm run dev`, port 5173). With localStorage and sessionStorage cleared, test and record pass/fail for each:
   - Landing renders at 1440px and 390px with no horizontal scroll. Every section is visible without scrolling animations. The CTAs route correctly with and without a session.
   - Guest path: landing → sign in → guest → onboarding → dashboard.
   - The sign-in mode's own path (A: form disabled; B: name validation and the greeting; C: register, log in, wrong password, expired token, server down).
   - Onboarding: Back and Continue on every step; Skip on every step; Escape; focus lands on each heading; keyboard-only from landing to dashboard; refresh mid-wizard returns to the same step; reduced motion has no animation.
   - Step 3 with the backend stopped: the notice and Try again; the dashboard is still reachable.
   - Text demo starts, and incidents appear on the dashboard through the existing WebSocket. The voice choice opens the Simulate window preselected and doesn't auto-start.
   - Replay intro and Sign out. A second visit doesn't show onboarding again for the same person.
   - Storage blocked (simulate by making `localStorage.setItem` throw in devtools): the app still works, and onboarding simply shows each visit.
3. Report: what passed and what failed; anything still visually off compared with the BizzNex screens and the mock; every hard-coded colour replaced in Step 1b; and any text/background pair below WCAG AA.

**Reference mock:** `design/nexus911-mock.html` (also published at https://claude.ai/artifact/TdaJsEGxa8CrZ6H2AmDHY5, private to its owner unless shared). The layouts, copy and colour treatment of all four screens should match it. Its dashboard screen is only an approximation; the real dashboard keeps its own layout and gets only the palette and the new header controls.

Commits: small and local, in the order above, plus a final `fix: …` commit per fix. **Do not push.**
