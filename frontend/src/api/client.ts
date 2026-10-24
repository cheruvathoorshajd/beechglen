// Typed client for every endpoint in README "API". VITE_USE_MOCKS=true serves src/mocks.
import type {
  AskNext,
  AuditEvent,
  Briefing,
  CallDetail,
  CallIn,
  IncidentDetail,
  IncidentSummary,
  Lead,
  LeadCreate,
  LeadUpdate,
  LinkDecision,
  Metrics,
  ProcessResult,
  QueueItem,
  RuntimeSettings,
  RuntimeSettingsPatch,
  SimStartRequest,
  SimStatus,
} from "./types";

export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function http<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const controller = new AbortController();
  const timer = init?.timeoutMs ? setTimeout(() => controller.abort(), init.timeoutMs) : undefined;
  try {
    const response = await fetch(path, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!response.ok) {
      let detail = response.statusText;
      try {
        const body = await response.json();
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
      } catch {
        /* keep statusText */
      }
      throw new ApiError(response.status, detail);
    }
    return (await response.json()) as T;
  } finally {
    if (timer) clearTimeout(timer);
  }
}

const json = (body: unknown): RequestInit => ({ body: JSON.stringify(body) });

type MockName =
  | "queue"
  | "incidents"
  | "incident"
  | "call"
  | "explain"
  | "ask-next"
  | "briefing"
  | "metrics"
  | "settings"
  | "sim-status";

const MOCKS: Record<MockName, () => Promise<{ default: unknown }>> = {
  queue: () => import("../mocks/queue.json"),
  incidents: () => import("../mocks/incidents.json"),
  incident: () => import("../mocks/incident.json"),
  call: () => import("../mocks/call.json"),
  explain: () => import("../mocks/explain.json"),
  "ask-next": () => import("../mocks/ask-next.json"),
  briefing: () => import("../mocks/briefing.json"),
  metrics: () => import("../mocks/metrics.json"),
  settings: () => import("../mocks/settings.json"),
  "sim-status": () => import("../mocks/sim-status.json"),
};

async function mock<T>(name: MockName): Promise<T> {
  const module = await MOCKS[name]();
  return structuredClone(module.default) as T;
}

const pick = <T>(name: MockName, live: () => Promise<T>) => (USE_MOCKS ? mock<T>(name) : live());

export const api = {
  postCall: (call: CallIn) => pick<ProcessResult>("call", () => http("/api/calls", { method: "POST", ...json(call) })),
  queue: () => pick<QueueItem[]>("queue", () => http("/api/queue")),
  call: (id: string) => pick<CallDetail>("call", () => http(`/api/calls/${encodeURIComponent(id)}`)),
  explain: (id: string) => pick<LinkDecision>("explain", () => http(`/api/calls/${encodeURIComponent(id)}/explain`)),
  askNext: (id: string) => pick<AskNext>("ask-next", () => http(`/api/calls/${encodeURIComponent(id)}/ask-next`)),
  incidents: () => pick<IncidentSummary[]>("incidents", () => http("/api/incidents")),
  incident: (id: string) => pick<IncidentDetail>("incident", () => http(`/api/incidents/${encodeURIComponent(id)}`)),
  briefing: (id: string) => pick<Briefing>("briefing", () => http(`/api/incidents/${encodeURIComponent(id)}/briefing`)),
  confirm: (callId: string) =>
    pick<ProcessResult>("call", () => http(`/api/links/${encodeURIComponent(callId)}/confirm`, { method: "POST" })),
  split: (callId: string) =>
    pick<ProcessResult>("call", () => http(`/api/links/${encodeURIComponent(callId)}/split`, { method: "POST" })),
  createLead: (body: LeadCreate) =>
    USE_MOCKS
      ? Promise.resolve<Lead>({ id: "lead-mock", status: "open", assigned_unit: null, ...body })
      : http<Lead>("/api/leads", { method: "POST", ...json(body) }),
  updateLead: (id: string, body: LeadUpdate) =>
    USE_MOCKS
      ? Promise.resolve<Lead>({
          id,
          incident_id: "",
          description: "",
          source_claim_ids: [],
          status: body.status ?? "open",
          assigned_unit: body.assigned_unit ?? null,
        })
      : http<Lead>(`/api/leads/${encodeURIComponent(id)}`, { method: "PATCH", ...json(body) }),
  settings: () => pick<RuntimeSettings>("settings", () => http("/api/settings")),
  putSettings: (patch: RuntimeSettingsPatch) =>
    pick<RuntimeSettings>("settings", () => http("/api/settings", { method: "PUT", ...json(patch) })),
  metrics: (timeoutMs?: number) => pick<Metrics>("metrics", () => http("/api/metrics", { timeoutMs })),
  audit: () => (USE_MOCKS ? Promise.resolve<AuditEvent[]>([]) : http<AuditEvent[]>("/api/audit")),
  startSim: (body: SimStartRequest) =>
    pick<SimStatus>("sim-status", () => http("/api/simulation/start", { method: "POST", ...json(body) })),
  stopSim: () => pick<SimStatus>("sim-status", () => http("/api/simulation/stop", { method: "POST" })),
  reset: () => pick<SimStatus>("sim-status", () => http("/api/reset", { method: "POST" })),
};

export function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof DOMException && error.name === "AbortError") return "The server took too long to answer.";
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}
