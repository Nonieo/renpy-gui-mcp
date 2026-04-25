import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Square, Download, Loader2, Settings, FileEdit } from "lucide-react";
import { api } from "@/api/client";
import { useWatcherEvent } from "@/api/ws";
import { LintBadge } from "@/layout/LintBadge";

interface PreviewStatus {
  running: boolean;
  pid?: number;
  last_pid?: number;
  last_exit_code?: number;
  already_running?: boolean;
  started?: boolean;
  stopped?: boolean;
  error?: string;
}

export function Header({ onOpenPrefs }: { onOpenPrefs: () => void }) {
  const meta = useQuery({
    queryKey: ["meta"],
    queryFn: () => api<{ project_root: string }>("/api/meta"),
  });
  const projectName = meta.data?.project_root.split("/").filter(Boolean).pop() ?? "";

  const preview = useQuery({
    queryKey: ["preview"],
    queryFn: () => api<PreviewStatus>("/api/preview"),
    // Poll every 2s — catches an external `stop_preview` from a different
    // MCP client (LLM harness) without forcing the user to refresh.
    refetchInterval: 2_000,
  });

  return (
    <header className="bg-card border-b border-line h-14 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-baseline gap-3 min-w-0">
        <span className="text-[10px] uppercase tracking-wide text-ink3">project</span>
        <span className="font-serif text-base text-ink truncate">
          {projectName || "(no project)"}
        </span>
        {meta.data && (
          <span className="text-[11px] text-ink3 font-mono truncate">
            {meta.data.project_root}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <WatcherPill />
        <LintBadge />
        <DraftingToggle />
        <button
          type="button"
          onClick={onOpenPrefs}
          className="p-1.5 text-ink3 hover:text-ink rounded-md hover:bg-cardAlt"
          title="Appearance & preferences"
          aria-label="Appearance"
        >
          <Settings className="w-4 h-4" />
        </button>
        <PreviewButton status={preview.data} />
        <button
          type="button"
          className="px-3 py-1.5 text-sm rounded-md text-white opacity-50 inline-flex items-center gap-1.5 cursor-not-allowed"
          style={{ background: "var(--rp-accent)" }}
          title="Distribution build is not yet wired (build_distribution MCP tool pending)"
          disabled
        >
          <Download className="w-4 h-4" /> Export .rpy
        </button>
      </div>
    </header>
  );
}

function WatcherPill() {
  const evt = useWatcherEvent();
  // Re-render once a second so the relative timestamp keeps moving without
  // depending on the next watcher event arriving.
  const [, tick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => tick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  if (!evt) {
    return (
      <span className="hidden md:inline-flex items-center gap-1.5 text-[11px] font-mono text-ink3">
        <span className="w-1.5 h-1.5 rounded-full bg-ink3" />
        watcher · idle
      </span>
    );
  }
  const filename = evt.path.split("/").pop() || evt.path;
  return (
    <span
      className="hidden md:inline-flex items-center gap-1.5 text-[11px] font-mono text-ink3 truncate max-w-[28ch]"
      title={`${evt.action}: ${evt.path}`}
    >
      <span
        className="w-1.5 h-1.5 rounded-full animate-pulse"
        style={{ background: "var(--rp-accent)" }}
      />
      watcher · {filename} · {relativeTime(evt.at)}
    </span>
  );
}

function relativeTime(at: Date): string {
  const seconds = Math.max(0, Math.round((Date.now() - at.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

function DraftingToggle() {
  // Phase 5 wires this to `set_drafting_mode`. Until then it's a visible
  // placeholder so the surface settles before the backend lands.
  return (
    <button
      type="button"
      disabled
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono text-ink3 border border-line opacity-60 cursor-not-allowed"
      title="Drafting mode lands in Phase 5 — set_drafting_mode + warp_to."
    >
      <FileEdit className="w-3.5 h-3.5" />
      drafting · off
    </button>
  );
}

function PreviewButton({ status }: { status: PreviewStatus | undefined }) {
  const qc = useQueryClient();
  const running = status?.running === true;

  const launch = useMutation({
    mutationFn: () => api<PreviewStatus>("/api/preview", { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["preview"] }),
  });
  const stop = useMutation({
    mutationFn: () => api<PreviewStatus>("/api/preview", { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["preview"] }),
  });

  const pending = launch.isPending || stop.isPending;
  const onClick = () => (running ? stop.mutate() : launch.mutate());
  const Icon = pending ? Loader2 : running ? Square : Play;

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={pending || !status}
      title={
        running
          ? `Stop the running Ren'Py preview (pid ${status?.pid})`
          : "Launch the project in Ren'Py"
      }
      className={
        running
          ? "px-3 py-1.5 text-sm rounded-md bg-rose-600 text-white hover:bg-rose-700 inline-flex items-center gap-1.5"
          : "px-3 py-1.5 text-sm rounded-md border border-line hover:bg-cardAlt inline-flex items-center gap-1.5 text-ink"
      }
    >
      <Icon className={pending ? "w-4 h-4 animate-spin" : "w-4 h-4"} />
      {pending ? "Working…" : running ? "Stop preview" : "Preview"}
    </button>
  );
}
