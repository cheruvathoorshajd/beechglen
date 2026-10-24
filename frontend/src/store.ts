import { create } from "zustand";
import { api, errorMessage } from "./api/client";
import type { IncidentDetail, IncidentSummary, Metrics, QueueItem, RuntimeSettings, SimStatus } from "./api/types";

export interface Toast {
  id: number;
  title: string;
  body: string;
  tone: "new-info" | "error" | "info";
}

interface ConsoleState {
  queue: QueueItem[];
  incidents: IncidentSummary[];
  incident: IncidentDetail | null;
  metrics: Metrics | null;
  settings: RuntimeSettings | null;
  simStatus: SimStatus | null;
  selectedIncidentId: string | null;
  selectedCallId: string | null;
  connected: boolean;
  loaded: boolean;
  toasts: Toast[];
  refresh: () => Promise<void>;
  selectIncident: (id: string | null) => void;
  selectCall: (callId: string | null, incidentId?: string) => void;
  setSimStatus: (status: SimStatus) => void;
  setSettings: (settings: RuntimeSettings) => void;
  setConnected: (connected: boolean) => void;
  pushToast: (toast: Omit<Toast, "id">) => void;
  dismissToast: (id: number) => void;
}

let toastSeq = 0;
let inflight: Promise<void> | null = null;
let queued = false;

export const useConsole = create<ConsoleState>((set, get) => ({
  queue: [],
  incidents: [],
  incident: null,
  metrics: null,
  settings: null,
  simStatus: null,
  selectedIncidentId: null,
  selectedCallId: null,
  connected: false,
  loaded: false,
  toasts: [],

  refresh: async () => {
    // Collapse bursts of events into one refetch at a time.
    if (inflight) {
      queued = true;
      return inflight;
    }
    inflight = (async () => {
      try {
        const [queue, incidents, metrics] = await Promise.all([api.queue(), api.incidents(), api.metrics()]);
        let selected = get().selectedIncidentId;
        if (selected && !incidents.some((i) => i.id === selected)) selected = null;
        if (!selected && incidents.length) selected = incidents[0].id;
        const incident = selected ? await api.incident(selected).catch(() => null) : null;
        set({ queue, incidents, metrics, incident, selectedIncidentId: selected, loaded: true });
      } catch (error) {
        set({ loaded: true });
        if (get().connected) get().pushToast({ title: "Refresh failed", body: errorMessage(error), tone: "error" });
      } finally {
        inflight = null;
        if (queued) {
          queued = false;
          void get().refresh();
        }
      }
    })();
    return inflight;
  },

  selectIncident: (id) => {
    set({ selectedIncidentId: id, selectedCallId: null });
    if (id) {
      api
        .incident(id)
        .then((incident) => {
          if (get().selectedIncidentId === id) set({ incident });
        })
        .catch(() => undefined);
    } else {
      set({ incident: null });
    }
  },

  selectCall: (callId, incidentId) => {
    if (incidentId && incidentId !== get().selectedIncidentId) get().selectIncident(incidentId);
    set({ selectedCallId: callId });
  },

  setSimStatus: (simStatus) => set({ simStatus }),
  setSettings: (settings) => set({ settings }),
  setConnected: (connected) => set({ connected }),

  pushToast: (toast) => {
    const id = ++toastSeq;
    set((state) => ({ toasts: [...state.toasts.slice(-3), { ...toast, id }] }));
    setTimeout(() => get().dismissToast(id), 6000);
  },
  dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
}));

/** First call time in the queue: the T+ origin. */
export function queueOrigin(queue: QueueItem[]) {
  if (!queue.length) return null;
  return queue.reduce((min, item) => (item.received_at < min ? item.received_at : min), queue[0].received_at);
}
