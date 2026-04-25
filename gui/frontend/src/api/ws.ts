import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

/**
 * The WebSocket subscription is opened once by `useFileWatcher` (called
 * at the App root) and feeds two consumers:
 *
 *   1. React-Query cache invalidation, so panels refetch on external edits.
 *   2. A module-level pub/sub surfacing the most recent watcher event for
 *      the Header's activity pill (and any future component that needs it).
 *
 * The pub/sub stays minimal — one current value plus a listener set —
 * because the watcher only emits one type of message and `useSyncExternalStore`
 * would be overkill for it.
 */

export interface WatcherEvent {
  kind: "rpy" | "asset";
  action: string;
  path: string;
  at: Date;
}

type Listener = (evt: WatcherEvent) => void;

let lastEvent: WatcherEvent | null = null;
const listeners = new Set<Listener>();

function emit(evt: WatcherEvent): void {
  lastEvent = evt;
  for (const l of listeners) l(evt);
}

/** Subscribe to the most recent watcher event. */
export function useWatcherEvent(): WatcherEvent | null {
  const [evt, setEvt] = useState<WatcherEvent | null>(lastEvent);
  useEffect(() => {
    const listener: Listener = (e) => setEvt(e);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
  return evt;
}

/**
 * Subscribe to the backend WebSocket. On every `file_change` event we
 * invalidate the relevant react-query keys so panels refetch
 * automatically, and we publish the event to the `useWatcherEvent`
 * subscribers.
 */
export function useFileWatcher() {
  const qc = useQueryClient();
  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws`);

    ws.onmessage = (msgEvt) => {
      try {
        const msg = JSON.parse(msgEvt.data);
        if (msg.type !== "file_change") return;
        // Coarse but cheap: invalidate everything; backend calls are fast and
        // the user only sees panels they're looking at.
        qc.invalidateQueries({ queryKey: ["overview"] });
        qc.invalidateQueries({ queryKey: ["labels"] });
        qc.invalidateQueries({ queryKey: ["graph"] });
        qc.invalidateQueries({ queryKey: ["characters"] });
        qc.invalidateQueries({ queryKey: ["images"] });
        qc.invalidateQueries({ queryKey: ["audio"] });
        qc.invalidateQueries({ queryKey: ["variables"] });
        qc.invalidateQueries({ queryKey: ["screens"] });

        emit({
          kind: msg.kind,
          action: msg.action,
          path: msg.path,
          at: new Date(),
        });
      } catch {
        // ignore malformed messages
      }
    };

    ws.onerror = () => {
      // Suppress noisy console output during development.
    };

    return () => ws.close();
  }, [qc]);
}
