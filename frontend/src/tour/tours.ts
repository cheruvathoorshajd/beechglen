// Feature tours for the console pages. Each step points at an element with a matching
// `data-tour` attribute. When the element isn't on screen yet (no calls, no incident
// selected), the step still shows, centered, so every feature gets explained.

export type TourId = "operator" | "officer" | "sim";

export interface TourStep {
  /** `data-tour` value of the element to point at. */
  target: string;
  title: string;
  body: string;
  /** Shown when the target isn't on screen yet. */
  missing?: string;
}

export const TOURS: Record<TourId, { title: string; steps: TourStep[] }> = {
  operator: {
    title: "Operator console",
    steps: [
      {
        target: "topbar",
        title: "Live status and the sim clock",
        body: "The dot shows whether the console is connected to the server. The clock is simulated time since the first call (T+) and says “running” while a scenario plays.",
      },
      {
        target: "queue",
        title: "The call queue",
        body: "Every 911 call, sorted by priority and then by age. The highest-priority call is always on top. Click a call to open its incident.",
        missing: "Calls appear here once a scenario starts. Start one from the Sim page.",
      },
      {
        target: "queue-card",
        title: "Reading a call card",
        body: "The number in the pill is the priority score (0–100): crimson at 80 and up, yellow outline 50–79, grey below 50. The band chip says how the call was linked. NEW INFO means the call added something the incident didn't know, so it gets priority even if it's a duplicate.",
        missing: "Call cards appear once calls arrive.",
      },
      {
        target: "map",
        title: "The incident map",
        body: "Each circle is one incident, not one call. Color shows severity and size shows how many calls were merged into it. Click a circle to open that incident.",
      },
      {
        target: "incident",
        title: "The incident panel",
        body: "Everything known about the selected incident: type, location and how confident the location is, plus when the first call came in and when dispatch was ready.",
        missing: "Select an incident on the map or a call in the queue to open this panel.",
      },
      {
        target: "consensus",
        title: "What callers report",
        body: "Each detail (suspect, weapon, vehicle…) shows every value callers gave, with its share and how many callers said it, including first-hand witnesses. It never shows only the winner.",
        missing: "Shown in the incident panel once an incident is selected.",
      },
      {
        target: "calls",
        title: "Calls, bands and Why linked?",
        body: "Bands: NEW started an incident, AUTO linked with high confidence, SUGGEST is a likely match waiting for you, CONFIRMED was approved by a person. “Why linked?” opens the evidence: the probability, each scored factor and any rule that blocked a link.",
        missing: "Shown in the incident panel once an incident is selected.",
      },
      {
        target: "call-actions",
        title: "Confirm and Split",
        body: "Confirm accepts the link (AUTO or SUGGEST becomes CONFIRMED). Split pulls a call out into its own new incident when it was merged by mistake. Both are recorded in the audit log.",
        missing: "These buttons sit on each call row in the incident panel.",
      },
      {
        target: "ask-next",
        title: "Ask next",
        body: "Questions to ask the caller on the line, based on what the incident is still missing. When the town is unclear, the town question is marked “Ask first”.",
        missing: "Shown below the incident panel once a call is selected.",
      },
      {
        target: "dispatch",
        title: "Dispatch package",
        body: "The units the dispatch rules recommend and the facts they rely on, each with its share and sources. Contested facts are marked. Units are illustrative, not real protocols.",
        missing: "Shown at the bottom of the incident panel.",
      },
    ],
  },
  officer: {
    title: "Officer view",
    steps: [
      {
        target: "officer-incidents",
        title: "Open incidents",
        body: "One card per incident with its top priority, location and how many calls were merged. “Dispatch ready” means enough is known to send units.",
        missing: "Incidents appear here once a scenario starts.",
      },
      {
        target: "officer-header",
        title: "Incident summary",
        body: "The incident type, location, location confidence, and the time from the first call to dispatch-ready.",
        missing: "Select an incident to see its summary.",
      },
      {
        target: "briefing",
        title: "Three-line briefing",
        body: "KNOWN is what callers agree on, DISPUTED is where they disagree, OPEN is what nobody has said yet. Short enough to read over the radio.",
        missing: "Select an incident to see its briefing.",
      },
      {
        target: "dispatch",
        title: "Dispatch package",
        body: "Recommended units and the facts behind them, with the share of callers who reported each one.",
        missing: "Select an incident to see its dispatch package.",
      },
      {
        target: "leads",
        title: "Leads board",
        body: "Follow-ups for officers, moved left to right: suggested → open → assigned → cleared. Add your own lead, or move one along when it's handled.",
        missing: "Select an incident to see its leads.",
      },
    ],
  },
  sim: {
    title: "Simulation",
    steps: [
      {
        target: "sim-scenario",
        title: "Pick a scenario",
        body: "Each scenario is a scripted set of synthetic 911 calls with real timings: the same events reported by different callers, in different words and languages.",
      },
      {
        target: "sim-speed",
        title: "Speed",
        body: "1× plays the calls in real time, so calls can be 30–60 seconds apart. 10× plays a 12-minute scenario in about 72 seconds. Pick 10× or 20× for a demo.",
      },
      {
        target: "sim-controls",
        title: "Start, Stop and Reset",
        body: "Start clears the console and replays the scenario from its first call. Stop pauses where it is and keeps the calls. Reset clears every call and incident.",
      },
      {
        target: "sim-progress",
        title: "Replay progress",
        body: "How many calls have arrived, the simulated clock, and whether the replay is running, stopped or finished. Open the Operator page while it runs to watch calls merge into incidents.",
      },
      {
        target: "sim-mass",
        title: "Mass-event mode",
        body: "For big events with many callers. Auto-linking needs a higher score (0.90) and the time window doubles, so separate incidents nearby are less likely to merge.",
      },
      {
        target: "sim-thresholds",
        title: "Thresholds",
        body: "Auto-link at: a call joins an incident on its own above this score. Suggest at: between the two, the link is suggested for a person to confirm. Time window: how far apart two calls can be and still match.",
      },
      {
        target: "sim-apply",
        title: "Apply & Replay",
        body: "Saves the thresholds, clears the console and replays the selected scenario, so you can see how the settings change the linking.",
      },
      {
        target: "metrics",
        title: "Metrics",
        body: "Live totals: calls, incidents, collapse rate (how many calls were merged into an existing incident), NEW INFO calls, calls per band, and how many caller claims were verified, pending or rejected.",
      },
    ],
  },
};
