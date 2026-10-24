# Nexus911 · 3-minute demo script

One presenter, one browser window at 1440×900. Total running time is about 2:55. The script uses all three scenarios. The robbery runs at 10× so there is time to talk over it; the Pike and Washington St scenarios run at 20×.

Every number below comes from a real replay of the scenarios with cached extractions. If you change the thresholds or mass-event mode, the numbers change.

## Before you record

1. Start both servers: `.venv/bin/python run.py` (port 8080) and `npm run dev` in `frontend/` (port 5173).
2. Open http://localhost:5173, choose **Continue as guest**, go through the intro and pick **Open the console** (not the demo).
3. Visit **Operator**, **Officer** and **Sim** once and press **Skip tour** on each guide, so no guide opens during the recording.
4. On **Sim**: mass-event mode **Off**, auto-link **0.85**, suggest **0.50**, time window **30 min**. Press **Reset**.
5. Close every toast and modal, and set the browser zoom to 100%.

## How the robbery timeline maps to the clock

Press Start at **0:20**. At 10×, a call at T+mm:ss arrives (mm×60+ss)/10 seconds later.

| Clock | Sim time | Call | What the system does |
|---|---|---|---|
| 0:20 | T+00:00 | c-0001 clerk (victim) | New incident, priority **90**, white jacket and jeans |
| 0:24–0:46 | T+00:40–04:20 | c-0002 … c-0009 | All **AUTO**-linked; priorities 0–22, so they sink. c-0004 is Spanish. c-0005 is hearsay ("neighbor said"), c-0007 is a repeat caller |
| 0:56 | T+06:00 | c-0010 knife near Newbury | AUTO at 0.89, priority **90**, NEW INFO · new weapon, new location |
| 1:00 | T+06:40 | c-0011 | AUTO, priority 0 |
| 1:32 | T+12:00 | c-0012 fire, people trapped, Westland Ave | **New** incident, priority **100**. Scored 0.49 because the type gate caps fire vs. robbery |

## Script

| Time | Screen | Do | Say |
|---|---|---|---|
| **0:00–0:15** | Operator (empty) | Nothing yet. | "When a crime happens on a busy street, a 911 center gets dozens of calls about the same thing. Every one is handled as new. Operators can't tell which caller is repeating and which one has something new. Nexus911 fixes that." |
| **0:15–0:22** | Sim | Select **Mass Ave robbery**, speed **10×**, press **Start**. | "These are scripted, synthetic calls with real timings. Twelve minutes of calls, played in about 72 seconds." |
| **0:22–0:35** | Operator | Switch to Operator. Point at the queue as calls land. | "The first call, from the store clerk, opens an incident at priority 90. Watch the next callers: they're linked to the same incident automatically and drop down the queue, to 13, 22, 9. Nothing is hidden. They're just ordered by what they add." |
| **0:35–0:55** | Operator, incident panel | Point at **What callers report** → upper clothing color. | "**Novelty one: every statement is its own claim in a knowledge graph**, with its caller and the exact quote. Seven callers say white jacket, three say black. A plain vote would say 70/30. **Novelty four: we weigh by independence.** One black-jacket report is secondhand, 'my neighbor said', and one is the same person calling twice. So it's 83% white, 17% black, and black stays visible." Point at the Spanish call c-0004: "This caller spoke Spanish. Values are stored in English and quotes stay in the original language, so it links like any other call." |
| **0:56–1:05** | Operator | The knife call c-0010 jumps to the top with a **NEW INFO** toast. Click it. | "**Novelty three: information-gain priority.** This caller is the eleventh about the same robbery, but they say the suspect pulled a knife near Newbury Street. New weapon, new location. It goes straight to the top at 90. A repeat goes down; new information goes up." |
| **1:05–1:20** | Why linked? on c-0010 | Click **Why linked?** on the knife call. Close it after the read-out. | "**Novelty five: explainable linking.** It scored 0.89, above the 0.85 auto-link line: same place, same time window, same suspect. Every factor is shown, so the operator can see exactly why it was merged." |
| **1:20–1:30** | Ask next panel | Point at the confirm line and the questions. | "Ask next gives the call-taker open questions only. It never puts an answer in the caller's mouth." Optional, if time allows: "**Novelty two, the hallucination guard:** every fact Claude extracts must quote the transcript word for word, or it's rejected." |
| **1:32–1:42** | Operator | The fire call c-0012 lands at **100**, top of the queue. Click it, then **Why linked?** | "A block away: smoke, people trapped on Westland Ave. It's close in place and time, but it's a fire, not a robbery. The type gate caps the score at 0.49, so it starts a **new** incident at priority 100. A new emergency is never buried under duplicates." |
| **1:42–1:50** | Robbery incident | Select the robbery incident. On one call row (e.g. c-0003), press **Split**. | "People stay in control. If a link is wrong, one click splits it into its own incident, and the change is logged in the audit trail." |
| **1:50–2:08** | Officer | Open **Officer**, select the robbery incident. Read the briefing. Press **Accept lead** on "Search along the suspect's direction of travel". | "The officer sees three lines: what's known, what's disputed, what's still open. The dispatch package is three police units and EMS on standby, routed to Boston Police and Boston EMS, with the share and sources behind each fact. Suggested leads go across the board from suggested to cleared." |
| **2:08–2:12** | Sim | Select **Pike crash**, speed **20×**, **Start**. | "Start clears the console. Now a crash on the Mass Pike." |
| **2:12–2:30** | Operator | Switch to Operator. Let the 12 calls arrive (about 19 s). Point at the location, the transfer banner and the vehicle color bars. | "**Novelty six: it knows Massachusetts.** Callers say 'exit 63', 'old exit 8', 'mile marker 62', 'the Turnpike', and one sends a text to 911. All twelve calls resolve to one place: I-90 eastbound, Exit 63, old Exit 8, Palmer. One call was transferred from the Palmer center to State Police, and the context came with it. The SUV color is contested, silver 58% against white 42%, so it's flagged instead of guessed. When a caller says the SUV is on fire, that call jumps to 90 as a new hazard. Dispatch: two EMS, Fire and State Police." |
| **2:30–2:45** | Sim → Operator | Select **Washington St**, **20×**, **Start**. Switch to Operator (about 8 s of calls). Click the call from the caller with no town. | "Washington Street exists in Boston, Brookline and Somerville. Two fights become two separate incidents, one at Downtown Crossing and one in Brookline. This third caller gave no town and has no device location, so it's only *suggested* for Boston, never auto-linked, and the first question to ask is 'Which town are you in?'. The fourth caller reports someone bleeding: new injury, priority 90." |
| **2:45–2:55** | Sim, Metrics | Scroll to **Metrics** (it shows this last run: 4 calls, 2 incidents). | "Live metrics show load as it happens. In our evaluation across all three scenarios, 28 calls collapse into 5 incidents, every new incident and every new-information call was caught, and every extracted claim was grounded in a quote. No call is ever dropped. AI suggests, people decide, and every decision is logged. That's Nexus911." |

## Novelty checklist

| # | Novelty | Where it shows |
|---|---|---|
| 1 | Claim-level knowledge graph | Robbery: "What callers report" keeps white and black, with sources |
| 2 | Quote-grounded hallucination guard | Spoken over ask-next; metrics show claims verified / pending / rejected |
| 3 | Information-gain priority | Knife call jumps to 90; repeats sit at 0–22 |
| 4 | Independence-aware witness weighting | 7–3 raw becomes 83%–17% |
| 5 | Explainable three-band linking | Why linked? on the knife call (0.89 auto) and the fire call (0.49, type gate); Split; Washington St suggest |
| 6 | Massachusetts-aware resolution | Pike old/new exits, mile marker, transfer; Washington St town ambiguity; Spanish caller |

## If something goes wrong

- **Calls don't appear:** check the top bar says **Live**. If it says Offline, the backend isn't running.
- **A guide opens mid-demo:** press Escape; it won't open again.
- **You fall behind:** skip the Split step and the optional guard line. The fire call still arrives at 1:32, and Officer can be cut to the briefing only.
- **Numbers differ:** press Reset on Sim and check the thresholds and mass-event mode are at their defaults.
