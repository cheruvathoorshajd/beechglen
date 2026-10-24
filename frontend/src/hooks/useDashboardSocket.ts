import { useEffect } from "react";
import { USE_MOCKS, api } from "../api/client";
import type { DashboardEvent, OverrideReason, RuntimeSettings, SimStatus } from "../api/types";
import { REASON_WORDS } from "../lib/format";
import { useConsole } from "../store";

/** Listens on /ws/dashboard, reconnects with backoff, and refetches on every event. */
export function useDashboardSocket() {
  useEffect(() => {
    const store = useConsole.getState();
    void store.refresh();
    api.settings().then(store.setSettings).catch(() => undefined);

    if (USE_MOCKS) {
      api.metrics().then(() => store.setConnected(true));
      api.startSim({ scenario_id: "mass_ave_robbery", speed: 10 }).then(store.setSimStatus);
      return;
    }

    let socket: WebSocket | null = null;
    let retry = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const connect = () => {
      const scheme = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${window.location.host}/ws/dashboard`);
      socket.onopen = () => {
        retry = 0;
        useConsole.getState().setConnected(true);
        void useConsole.getState().refresh();
      };
      socket.onmessage = (message) => {
        let event: DashboardEvent;
        try {
          event = JSON.parse(message.data as string) as DashboardEvent;
        } catch {
          return;
        }
        const state = useConsole.getState();
        if (event.type === "sim.status") state.setSimStatus(event.payload as unknown as SimStatus);
        if (event.type === "settings.updated") state.setSettings(event.payload as unknown as RuntimeSettings);
        if (event.type === "call.processed" && event.payload.new_info) {
          const reasons = (event.payload.override_reasons as OverrideReason[] | undefined) ?? [];
          state.pushToast({
            title: `NEW INFO · ${String(event.payload.call_id)}`,
            body: reasons.map((reason) => REASON_WORDS[reason] ?? reason).join(", "),
            tone: "new-info",
          });
        }
        void state.refresh();
      };
      socket.onclose = () => {
        useConsole.getState().setConnected(false);
        if (stopped) return;
        retry += 1;
        timer = setTimeout(connect, Math.min(5000, 500 * 2 ** retry));
      };
      socket.onerror = () => socket?.close();
    };

    connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socket?.close();
    };
  }, []);
}
