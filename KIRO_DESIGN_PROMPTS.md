# Nexus911 design port: Kiro prompts

Replicates the team's design package (logo palette, BizzNex type and screen patterns, four-screen flow) in this repo's frontend, with this repo's content.

## 1. Setup (you, 0 credits)

1. Copy the teammate's design folder into the repo root as `design/`: `Nexus911.png`, `STYLE_GUIDE.html`, `nexus911-mock.html`, `PORT_PLAN.md`, `FRONTEND_BUILD_PROMPT.md` and `README.md`.
2. Save `V2_SCREENS.md` as `design/V2_SCREENS.md`.
3. Save `style-guide.md` as `.kiro/steering/style-guide.md`.
4. Commit and push:

```bash
git add design .kiro/steering/style-guide.md
git commit -m "design: add style guide, mock and screen spec"
git push
```

BizzNex isn't needed: the mock already carries its patterns. Don't paste `design/FRONTEND_BUILD_PROMPT.md` into Kiro; it targets the v1 repo.

## 2. Kick-off prompt (paste once)

```text
Our teammate's design package is now in design/, and the rules distilled from it are in .kiro/steering/style-guide.md. Replicate that design in this repo's frontend. Follow the terminal rules in context.md throughout: start every command with the repo-root cd, make one tool call at a time, and run long jobs in the background with the exit marker.

Read first: .kiro/steering/style-guide.md, design/V2_SCREENS.md, context.md, and the CSS in design/nexus911-mock.html and design/STYLE_GUIDE.html. Then inspect frontend/ to see which C1 tasks already exist.

Precedence:
- The design package was written for Nexus911 v1, a different repo with Tailwind v4, voice mode, a scenarios endpoint and different content. Don't run design/FRONTEND_BUILD_PROMPT.md, and don't copy the mock's v1 wording. Use the mock and design/PORT_PLAN.md only for layout, interaction and CSS.
- README.md decides behavior, data and endpoints. style-guide.md decides how things look. design/V2_SCREENS.md decides the words and behavior of the landing, sign-in and onboarding screens.

Recorded decisions (add them to context.md and don't revisit them):
- Keep Tailwind 3. Put the tokens on :root in src/index.css and mirror them in tailwind.config.js theme.extend (colors, fontFamily, borderRadius). No Tailwind v4 @theme.
- Fonts come from @fontsource packages imported in src/main.tsx, so Vite bundles them and the demo works offline: @fontsource-variable/fraunces (roman and italic; include the opsz axis if the package offers it), @fontsource/ibm-plex-sans 400, 500, 600, 700 and italic 400, and @fontsource/ibm-plex-mono 400 and 500. Use latin-only files if the packages provide them. The variable package registers the family as "Fraunces Variable", so the serif stack is "Fraunces Variable", Fraunces, Georgia, serif. No Google Fonts link and no Outfit.
- The font packages are the only new dependencies. Icons come from a small inline-SVG Icon component built from the <symbol>s in design/nexus911-mock.html (24×24, 1.8 stroke). Add new icons in the same style only when needed.
- Landing, sign-in and onboarding port the mock's class-based CSS into plain CSS files (landing.css, auth.css, onboarding.css), renaming --accent to --brand, --accent-rule to --brand-rule, --accent-tint to --brand-tint, and --bad to --brand. Console components keep Tailwind with the theme tokens.
- No backend changes. Sign-in is name only and kept in the browser, and guests get every feature.
- The map darkens the OpenStreetMap tiles with a CSS filter. Offline, tiles don't load; everything else still works.

Stages (add them to context.md as a checklist, then work through them in order, one commit each):
- D1 Foundations. Update README.md "Frontend" (routes /, /signin, /welcome, the console at /operator, /officer and /sim, the design/ folder, a pointer to the style guide) and the frontend section of .kiro/steering/tech.md (point to style-guide.md; priority colors become brand, warn and ink-soft). Install the font packages in the background with the exit marker. Add the tokens, the base styles (body, :focus-visible, text-wrap: balance, reduced motion) and these primitives in src/ui/: Wordmark, Button, Badge, Tag, SpecLabel, ConfidenceBar, Field, Segmented, ChoiceCard, Disc, Bloom, LiveDot, Icon. Remove off-palette colors from the existing frontend code.
- D2 Console. Apply the "Console mapping" in style-guide.md to every console page and component that exists, and build any C1 task that isn't done yet directly in the new style, so nothing is built twice. Put the Wordmark in the top bar. Add Vitest tests for the priority pill thresholds and for the Critical badge showing its word.
- D3 Landing at / per design/V2_SCREENS.md. The console's default route becomes /operator. Until D4 is done, the landing CTAs go to /operator.
- D4 The session module, route guard, sign-in screen and console header controls (who chip, Replay intro, Sign out) per design/V2_SCREENS.md. Add Vitest tests for session.ts (including storage that throws), the guard's redirects and the name validation.
- D5 The onboarding wizard per design/V2_SCREENS.md, with Vitest tests for Escape skipping, focus moving to each heading, and the server-down state.
- D6 Verify. Run the full backend suite, the frontend build and Vitest, each in the background with the exit marker. Grep frontend/src for hex values, rgb(), rgba() and Tailwind color utilities outside the token files, and fix or list each one. List every text/background pair you used with its contrast ratio, and flag anything under 4.5:1 for body text or 3:1 for large text and UI. Update README.md and context.md, then give me a short list of what to check in a browser.

After each stage, run a background build and Vitest, update context.md, and commit as "stage-8.D<N>: <summary>". Don't push. Keep going to the next stage unless something fails twice or needs a decision from me.
```

## 3. Continue prompt (when a session stops)

```text
Read context.md. Continue with the next unchecked design stage (D1–D6), following .kiro/steering/style-guide.md, design/V2_SCREENS.md and the terminal rules and recorded decisions in context.md. Verify it with a background build and Vitest, update context.md, and commit as "stage-8.D<N>: <summary>". Keep going unless something fails twice or needs a decision from me.
```

## 4. Your browser check (after D6)

Run `python run.py` and `npm --prefix frontend run dev`, then check:

- **Landing** at full width and at 390px (devtools device mode): nothing scrolls sideways, the disc sits behind the headline, and every section shows without scrolling animations.
- **Guest path:** Get started → Continue as guest → onboarding → console.
- **Name path:** an empty name and an invalid name each show their error; a valid name gets "Welcome, <name>."
- **Onboarding:** Back and Continue, Skip on every step, Escape, keyboard only (Tab stays inside, arrow keys switch cards), and a refresh mid-wizard returns to the same step.
- **Server down:** stop the backend and open step 3. You should see the notice and Try again, and the console is still reachable.
- **Demo:** Run the demo. The queue fills, duplicates sink, the knife call shows NEW INFO, and the fire call jumps to the top with the Critical badge and stripe.
- **Replay intro and Sign out** work, and a second visit with the same name skips onboarding.
- **Reduced motion** (OS setting): no animation, and every screen still looks complete.
- **Offline** (Wi-Fi off, `DEMO_MODE=offline`): the fonts still render and only the map tiles are blank.
- Compare each screen with `design/nexus911-mock.html` side by side.

## If time runs short

D1 and D2 are what judges see during the demo, so finish those first. Then cut in this order: D5 onboarding, then D4 sign-in (the landing CTAs go straight to `/operator`), then D3 landing.
