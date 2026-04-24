import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

/**
 * Subscribe to the backend WebSocket. On every file_change event we invalidate
 * the relevant react-query keys so panels refetch automatically.
 */
export function useFileWatcher() {
  const qc = useQueryClient();
  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${window.location.host}/ws`);

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
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
