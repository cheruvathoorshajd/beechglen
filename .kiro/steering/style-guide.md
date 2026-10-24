---
inclusion: always
---

# Nexus911 style guide (frontend rules)

Distilled from `design/STYLE_GUIDE.html` and `design/nexus911-mock.html`. Open both in a browser for the visual reference. The words and behavior of the landing, sign-in and onboarding screens are in `design/V2_SCREENS.md`.

The design package was written for Nexus911 v1. In this repo, README.md decides behavior, data and endpoints, this file decides how things look, and `design/V2_SCREENS.md` decides the copy. Never copy the mock's v1 wording (voice agents, Gemini, competitor table, national statistics, highway-accident callers).

## Principles

1. **Calm under pressure.** Black ground, white type, little ornament. Urgency is shown by state (Critical badge, crimson stripe, priority number), never by flashing or busy layout.
2. **One red, used with intent.** Crimson means "Nexus911" or "critical". It never decorates and is never a hover color.
3. **Every fact shows its evidence.** Share, source count and contested flag sit beside every fact, in the same place every time.
4. **Three voices.** Fraunces serif is the human voice (headlines, incident titles, big numbers). IBM Plex Sans carries text and controls. IBM Plex Mono is the machine voice (labels, numbers, timestamps, badges, table headers).
5. **Honest about the prototype.** Synthetic calls, no real accounts and no real dispatch are stated on the landing page, at sign-in and in onboarding.

## Tokens

CSS variables on `:root` in `frontend/src/index.css`, mirrored in `tailwind.config.js` `theme.extend`. Dark only (`color-scheme: dark`).

| Token | Value | Use |
|---|---|---|
| `--ground` | `#000000` | Page background |
| `--card` | `#0C0C0C` | Panels, sign-in story panel, onboarding rail |
| `--raised` | `#161616` | Raised rows, incident cards, selected segments |
| `--ink` | `#FFFFFF` | Headings and body text |
| `--ink-soft` | `#A3A3A3` | Secondary text, labels, captions (8.3:1) |
| `--rule` | `rgba(255,255,255,.14)` | Borders, inputs |
| `--rule-soft` | `rgba(255,255,255,.08)` | Hairline dividers |
| `--brand` | `#C00000` | The only red: fills, icons, dots, rules, large type, Critical |
| `--brand-rule` | `#B40000` | Underline rules: wordmark, emphasised words, band top |
| `--brand-tint` | `rgba(192,0,0,.18)` | Focus halos, selected-card glow, icon tiles |
| `--ok` | `#22C55E` | Confirmed, high confidence, Live dot |
| `--warn` | `#EAB308` | Contested, mid priority, prototype notice, limitations |
| `--ease` | `cubic-bezier(.22,1,.36,1)` | All motion |
| `--radius` | `3px` | Buttons, inputs, cards, panels, tags. Pills (999px) only for badges; 50% only for dots and the disc |

Fonts: `--serif: "Fraunces Variable", Fraunces, Georgia, serif` · `--sans: "IBM Plex Sans", system-ui, -apple-system, sans-serif` · `--mono: "IBM Plex Mono", ui-monospace, monospace`. Bundled from @fontsource with `font-display: swap`. No other families.

## Contrast (WCAG AA)

- White on black 21:1. `#A3A3A3` on black 8.3:1, for all secondary text. White on crimson 6.48:1, for text on any crimson fill.
- Crimson on black is 3.24:1: only for large text (24px+, or 18.66px+ bold), icons, dots, rules, borders and focus rings.
- **Never small crimson text.** Use white text with a crimson dot, rule or underline beside it. (The mock's `.field-err` uses crimson text; follow the guide's `.ferr` instead: white text with a crimson ✕.)
- Crimson fills always carry white text.
- No cyan, blue, purple or slate accents, no gradient text, no decorative glows. No shadows except the 3–4px `--brand-tint` focus or selected halo.

## Type scale

| Role | Font | Size | Line-height | Tracking | Weight |
|---|---|---|---|---|---|
| Landing hero | serif | clamp(2.8rem, 8vw, 6.4rem) | .98 | −.04em | 500 |
| Onboarding heading | serif | clamp(2.1rem, 4.6vw, 3.4rem) | 1.02 | −.035em | 500 |
| Section or page title | serif | clamp(1.7rem, 3.2vw, 2.4rem) | 1.08 | −.02em | 500 |
| Pull quote | serif italic | clamp(1.5rem, 3.4vw, 2.5rem) | 1.25 | −.015em | 400 |
| Stat number | serif | clamp(2.6rem, 5vw, 3.6rem) | 1 | −.03em | 500 |
| Incident title | serif | 19–24px | 1.2 | −.01em | 500 |
| Lede | sans | 16.5–18px | 1.55 | 0 | 400 |
| Body | sans | 15px | 1.6 | −.006em | 400 |
| Button | sans | 14px (sm 13px) | | −.01em | 500 |
| Card title | sans | 15–16px | | −.01em | 600 |
| Spec label | mono | 11.5px | | .2em, uppercase | 500 |
| Field label, caption, table header, badge | mono | 10–11px | | .04–.14em | 400–500 |
| Wordmark | serif "NEXUS" + sans "911" | 19px | 1 | .16em, uppercase | 400 / 700 |

Numbers (priority, shares, counts, T+) are mono with `font-variant-numeric: tabular-nums`. Headlines use `text-wrap: balance` and stay around 20 characters. Body reading width 52–58ch.

## Logo motifs

- **Wordmark** component on every screen: "NEXUS" in serif 400, uppercase, .16em tracking, white; "911" in sans 700, crimson, 1.05em; a 2px `--brand-rule` underline under the lockup.
- **Disc**: a flat crimson circle, no blur or gradient. Only two places: behind the landing hero headline (`width: min(44vw, 470px)`, 230px on phones) and cropped into the sign-in story panel's corner. Text over it stays white; no grey text on the disc.
- **Underline**: emphasised words are white italic with a crimson underline (`text-decoration-color: var(--brand-rule)`), never crimson text.
- **Dot**: a 6px crimson dot before the key part of spec labels, and the logo's "• Emergency dispatching, simplified •" in the landing colophon.
- **Bloom**: the onboarding uses a soft crimson glow (radial-gradient of brand at 30%, blur 70px, opacity .5) instead of a disc, so step text stays readable.

## Layout

Side gutters 16px on phones and 48px at 900px and up, written with `max()` and safe-area insets. Spacing steps 6 · 12 · 20 · 34 · 56 · 92 · 140; section padding `clamp(56px, 8vw, 92px)`. Hairlines (1px `--rule-soft`) separate sections and list rows instead of boxes. Breakpoints 980 · 860 · 760 · 640 · 520px. No sideways scroll at 390px.

## Components

- **Buttons.** Primary: crimson fill, white text, one main action per screen. Ghost: 1px `--rule` border. Quiet: `--ink-soft` text, for Back, Skip and Sign out. `sm` size. Disabled: opacity .36 and a not-allowed cursor. Hover changes border or brightness only (160–200ms); press moves 1px down.
- **Spec label.** Mono 11.5px uppercase, .2em tracking. Key part white with the crimson dot, the rest grey: "STEP 2 OF 3 · HOW TO READ IT".
- **Badge.** Mono 10px uppercase pill, 1px `--rule` border, grey text, always containing a word. Only Critical is filled (crimson, white text). Highlight badges use a crimson border with white text.
- **Tag.** Square, crimson fill, white mono 10px ("Recommended").
- **Confidence bar.** 4px track in `--rule-soft`; the fill grows from 0 to its value in 900ms. The value and source count are printed beside it in mono ("83% · 7 sources"), so the color is never the only signal.
- **Contested.** △ glyph plus the word, in `--warn`, with a one-line reason.
- **Field.** Mono uppercase label above, 3px-radius input, focus = crimson border plus 3px `--brand-tint` halo. Invalid = crimson border, `aria-invalid`, `aria-describedby`, white error text with a crimson ✕ that says how to fix it, and focus returns to the field.
- **Step rail.** 26px circles with mono numbers. Current: crimson ring and 4px halo. Done: crimson fill with a tick. Upcoming: grey outline.
- **Choice card.** 1px `--rule` border. Selected: crimson border, 3px halo and a filled tick. Hover: border `--ink-soft`.
- **Segmented control.** The selected option uses `--raised` grey, not red.
- **Live indicator.** Green dot plus "LIVE" in mono, with a 1.6s opacity pulse (the only looping animation).
- **Icons.** Inline SVG from the mock's `<symbol>`s: 24×24, 1.8 stroke, round caps. Crimson icons sit on `--brand-tint` tiles.
- **Focus.** A 2px crimson outline with a 2px offset on every control.
- Don't port the mock's prototype tab bar (`.proto`); it exists only to switch screens in the mock.

## Console mapping (README data)

- **Priority pill** (0–100, always shows the number): 80+ crimson fill with white text; 50–79 `--warn` border and text; below 50 `--rule` border with `--ink-soft` text.
- **Critical**: incident severity 0.9 or above (shooting, stabbing, fire, weapon, trapped, not breathing) shows a filled "Critical" badge and a 3px crimson left stripe on its incident card and queue cards. Never color alone.
- **Band chips**: AUTO neutral; SUGGEST `--warn` border ("needs you"); NEW crimson border with white text; CONFIRMED `--ok` border with ✓.
- **NEW INFO badge**: crimson border, white text, with the reasons in words ("new weapon", "new hazard").
- **Language, channel and role chips**: neutral badges.
- **Consensus bars**: every value, never just the winner. The top value's bar is `--ok` when not contested and `--warn` when contested; other values are `--ink-soft`. Mono "share · sources · first-hand".
- **Contradictions**: △ in `--warn` with the values in words.
- **Why linked? modal**: card with the components (geo, time, type, entity, weights) in a mono table, gates in plain words ("Different emergency types are never merged"), and decided_by.
- **Dispatch package**: mono field labels, value, share and sources; contested marked △; a neutral "Illustrative" badge (not the crimson tag).
- **Transfer banner**: 2px `--rule` left border, mono "Transferred from palmer-local · context preserved".
- **Map**: darken the OpenStreetMap tiles with a CSS filter on `.leaflet-tile-pane` (grayscale, invert, lower brightness). Markers are crimson (priority 80+), `--warn` (50–79) or grey (below 50), sized by call count, with a white ring when selected. Popups and controls use card colors.
- **Officer briefing**: three rows with spec labels KNOWN · DISPUTED · OPEN. **Leads board**: mono column headers with counts; status badges.
- **Sim page**: scenario choice cards, speed as a segmented control, Start (primary), Stop (ghost), Reset (quiet), mass-event as a segmented ON/OFF, range inputs with `accent-color: var(--brand)`, metric figures in serif with mono labels (crimson only for a large critical count).
- **Toasts**: card with a 3px crimson left stripe for NEW INFO, with the reasons in words.
- **Panels**: `--card` ground, 1px `--rule-soft` border, 3px radius. No 12px rounded glass cards, no shadows.

## Motion

Screen change: 350ms fade. Onboarding step: 450ms fade up 14px. Progress bar: 500ms. Confidence bar: 900ms. Hover and press: 160–200ms. Live dot: 1.6s pulse. All use `--ease`. Under `prefers-reduced-motion: reduce`, every animation and transition is off and each screen still looks complete.

## Accessibility

Body text at least 4.5:1. Every colored state also has a word or glyph (● Critical, △ contested, ✕ errors, the value beside each bar). Real `<table>`s with headers, scrolling sideways inside their own container on phones. The onboarding is a modal dialog: focus moves to each step's heading, Tab stays inside, Escape skips, arrow keys move between the start choices. Storage failures (private mode) never break the flow.

## Writing

Say what a control does ("Run the demo", "Open the console", "Replay intro"), never "Submit" or "OK". Errors say how to fix the problem. Name things the way operators know them ("confidence", "sources", "contested"). State limits plainly. Keep headlines around 20 characters. Every number must come from README.md or measured output.
