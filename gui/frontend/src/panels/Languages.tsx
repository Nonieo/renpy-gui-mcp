/**
 * Languages — translation coverage dashboard (Phase 8).
 *
 * Reads `/api/translations/coverage` for per-language progress bars and
 * `/api/translations/stale?language=…` for the stale-string list.
 * `/api/translations/scaffolding/{language}` regenerates the scaffolding
 * via Ren'Py's own translate command.
 *
 * SDK-gated tools surface their stdout/stderr in the response so the
 * panel can show what Ren'Py reported.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Languages as LanguagesIcon, Plus, RefreshCw } from "lucide-react";
import { api } from "@/api/client";
import type {
  StaleTranslations,
  TranslationCoverage,
  TranslationCoverageRow,
} from "@/api/types";

export function Languages() {
  const qc = useQueryClient();
  const [selected, setSelected] = useState<string | null>(null);
  const [scaffoldName, setScaffoldName] = useState("");
  const [error, setError] = useState<string | null>(null);

  const coverageQ = useQuery({
    queryKey: ["translation-coverage"],
    queryFn: () => api<TranslationCoverage>("/api/translations/coverage"),
  });

  // Auto-select the first language once coverage loads.
  useEffect(() => {
    if (selected) return;
    const first = coverageQ.data?.languages[0]?.language;
    if (first) setSelected(first);
  }, [coverageQ.data, selected]);

  const staleQ = useQuery({
    queryKey: ["stale-translations", selected],
    queryFn: () =>
      api<StaleTranslations>(
        `/api/translations/stale${selected ? `?language=${encodeURIComponent(selected)}` : ""}`,
      ),
    enabled: !!selected,
  });

  const scaffold = useMutation({
    mutationFn: async (language: string) => {
      setError(null);
      return api<{ language?: string; returncode?: number; stderr?: string; error?: string }>(
        `/api/translations/scaffolding/${encodeURIComponent(language)}`,
        { method: "POST" },
      );
    },
    onSuccess: (data, lang) => {
      if (data.error) {
        setError(data.error);
        return;
      }
      if (typeof data.returncode === "number" && data.returncode !== 0) {
        setError(data.stderr || `renpy.sh translate exited ${data.returncode}`);
        return;
      }
      qc.invalidateQueries({ queryKey: ["translation-coverage"] });
      qc.invalidateQueries({ queryKey: ["stale-translations"] });
      setSelected(lang);
      setScaffoldName("");
    },
    onError: (err) => setError(String(err)),
  });

  return (
    <div className="w-full h-full overflow-auto bg-canvas">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <header className="border-b border-line pb-3">
          <span className="text-[10px] uppercase tracking-wide text-ink3 font-mono">
            Coverage
          </span>
          <h1 className="font-serif text-2xl text-ink mt-1 flex items-center gap-2">
            <LanguagesIcon className="w-5 h-5" />
            Languages
          </h1>
          <p className="text-xs text-ink3 mt-1">
            Per-language translation progress, sourced from{" "}
            <code className="font-mono">game/tl/&lt;lang&gt;/</code>.
          </p>
        </header>

        {coverageQ.isLoading && <p className="text-ink3 text-sm">Loading coverage…</p>}
        {coverageQ.error && (
          <p className="text-rose-600 text-sm">Error: {String(coverageQ.error)}</p>
        )}

        {coverageQ.data && coverageQ.data.languages.length === 0 && (
          <div className="bg-card border border-line rounded p-4 text-sm text-ink2">
            <p>
              No translations exist yet. Add a language below to scaffold one via
              Ren'Py's <code className="font-mono">translate</code> command.
            </p>
          </div>
        )}

        {coverageQ.data && coverageQ.data.languages.length > 0 && (
          <ul className="space-y-2">
            {coverageQ.data.languages.map((row) => (
              <CoverageRow
                key={row.language}
                row={row}
                selected={selected === row.language}
                onSelect={() => setSelected(row.language)}
                onRefresh={() => scaffold.mutate(row.language)}
                refreshing={scaffold.isPending && scaffold.variables === row.language}
              />
            ))}
          </ul>
        )}

        <section className="bg-card border border-line rounded p-4 flex items-center gap-2">
          <Plus className="w-4 h-4 text-ink3" />
          <input
            value={scaffoldName}
            onChange={(e) => setScaffoldName(e.target.value)}
            placeholder="add language (e.g. spanish)"
            className="flex-1 px-2 py-1 border border-line rounded text-xs font-mono bg-card text-ink"
          />
          <button
            onClick={() => scaffoldName.trim() && scaffold.mutate(scaffoldName.trim())}
            disabled={!scaffoldName.trim() || scaffold.isPending}
            className="px-3 py-1.5 rounded text-xs text-white disabled:opacity-50"
            style={{ background: "var(--rp-accent)" }}
          >
            {scaffold.isPending ? "Scaffolding…" : "Scaffold"}
          </button>
        </section>

        {error && (
          <div className="bg-rose-50 border border-rose-200 rounded p-3 text-xs text-rose-700">
            {error}
          </div>
        )}

        {selected && (
          <section>
            <header className="flex items-baseline justify-between mb-2">
              <h2 className="font-serif text-base text-ink">
                Stale strings · {selected}
              </h2>
              <span className="text-[10px] font-mono text-ink3">
                {staleQ.data?.count ?? 0} entries
              </span>
            </header>
            {staleQ.isLoading && <p className="text-ink3 text-sm">Loading…</p>}
            {staleQ.data && staleQ.data.count === 0 && (
              <p className="text-ink3 text-sm">
                Nothing stale — every entry has a non-empty translation that differs
                from its source.
              </p>
            )}
            {staleQ.data && staleQ.data.count > 0 && (
              <ul className="bg-card border border-line rounded divide-y divide-line">
                {staleQ.data.stale.map((entry, i) => (
                  <li key={i} className="px-3 py-2 text-xs">
                    <div className="flex items-baseline justify-between gap-2">
                      <span
                        className="text-[10px] font-mono uppercase tracking-wide rounded px-1.5 py-0.5 bg-cardAlt text-ink2"
                      >
                        {entry.kind}
                      </span>
                      <span className="font-mono text-[10px] text-ink3">
                        {entry.file}:{entry.line}
                      </span>
                    </div>
                    {entry.source && (
                      <div className="font-serif text-ink mt-1">"{entry.source}"</div>
                    )}
                    <div className="font-mono text-ink3 mt-0.5">
                      {entry.target ? `→ "${entry.target}" (matches source)` : "→ (empty)"}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </div>
  );
}

function CoverageRow({
  row,
  selected,
  onSelect,
  onRefresh,
  refreshing,
}: {
  row: TranslationCoverageRow;
  selected: boolean;
  onSelect: () => void;
  onRefresh: () => void;
  refreshing: boolean;
}) {
  return (
    <li>
      <div
        className={[
          "flex items-center gap-3 px-3 py-2 rounded border bg-card transition-colors cursor-pointer",
          selected ? "border-ink" : "border-line hover:border-ink2",
        ].join(" ")}
        onClick={onSelect}
      >
        <span className="font-mono text-sm text-ink min-w-24">{row.language}</span>
        <div className="flex-1 h-2 bg-cardAlt rounded overflow-hidden">
          <div
            className="h-full"
            style={{
              width: `${row.percent}%`,
              background: "var(--rp-accent)",
            }}
          />
        </div>
        <span className="text-[11px] font-mono text-ink2 min-w-16 text-right">
          {row.translated}/{row.total}
        </span>
        <span className="text-[11px] font-mono text-ink2 min-w-12 text-right">
          {row.percent}%
        </span>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRefresh();
          }}
          disabled={refreshing}
          className="ml-1 p-1 text-ink3 hover:text-ink rounded disabled:opacity-50"
          title="Re-run renpy.sh translate to refresh scaffolding"
        >
          <RefreshCw className={refreshing ? "w-3.5 h-3.5 animate-spin" : "w-3.5 h-3.5"} />
        </button>
      </div>
    </li>
  );
}
