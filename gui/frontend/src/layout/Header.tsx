import { useQuery } from "@tanstack/react-query";
import { Play, Download } from "lucide-react";
import { api } from "@/api/client";

export function Header() {
  const meta = useQuery({
    queryKey: ["meta"],
    queryFn: () => api<{ project_root: string }>("/api/meta"),
  });
  const projectName = meta.data?.project_root.split("/").filter(Boolean).pop() ?? "";

  return (
    <header className="bg-card border-b border-zinc-200 h-14 flex items-center justify-between px-6 shrink-0">
      <div className="text-sm text-zinc-600">
        <span className="font-mono text-zinc-900">{projectName || "(no project)"}</span>
        {meta.data && (
          <span className="ml-3 text-xs text-zinc-400 font-mono">{meta.data.project_root}</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="px-3 py-1.5 text-sm rounded-md border border-zinc-200 hover:bg-zinc-50 inline-flex items-center gap-1.5"
          title="Launch the project in Ren'Py (not yet wired)"
          disabled
        >
          <Play className="w-4 h-4" /> Preview
        </button>
        <button
          type="button"
          className="px-3 py-1.5 text-sm rounded-md bg-accent text-white hover:bg-indigo-600 inline-flex items-center gap-1.5"
          title="Build distributables (not yet wired)"
          disabled
        >
          <Download className="w-4 h-4" /> Export .rpy
        </button>
      </div>
    </header>
  );
}
