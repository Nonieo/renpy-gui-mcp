import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Square, Download, Loader2 } from "lucide-react";
import { api } from "@/api/client";

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

export function Header() {
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
    <header className="bg-card border-b border-zinc-200 h-14 flex items-center justify-between px-6 shrink-0">
      <div className="text-sm text-zinc-600 min-w-0">
        <span className="font-mono text-zinc-900">{projectName || "(no project)"}</span>
        {meta.data && (
          <span className="ml-3 text-xs text-zinc-400 font-mono truncate">
            {meta.data.project_root}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <PreviewButton status={preview.data} />
        <button
          type="button"
          className="px-3 py-1.5 text-sm rounded-md bg-accent text-white opacity-50 inline-flex items-center gap-1.5 cursor-not-allowed"
          title="Distribution build is not yet wired (build_distribution MCP tool pending)"
          disabled
        >
          <Download className="w-4 h-4" /> Export .rpy
        </button>
      </div>
    </header>
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
          : "px-3 py-1.5 text-sm rounded-md border border-zinc-200 hover:bg-zinc-50 inline-flex items-center gap-1.5"
      }
    >
      <Icon className={pending ? "w-4 h-4 animate-spin" : "w-4 h-4"} />
      {pending ? "Working…" : running ? "Stop preview" : "Preview"}
    </button>
  );
}
