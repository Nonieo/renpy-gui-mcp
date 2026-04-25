/**
 * Choice View — the second canvas (Phase 6).
 *
 * Derived filter over the same data as Story Map: every top-level
 * `menu:` in the project, with its branches rendered as choice pills.
 * Player perspective — what happens when I pick X?
 *
 * Read-mostly: clicking a pill jumps the Inspector to the target
 * label. Dragging an existing target to a different label would call
 * `redirect_jump` (line-precise via `target_line`); deferred until the
 * Inspector exposes per-event drag affordances.
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, AlertCircle } from "lucide-react";
import { api } from "@/api/client";
import type { ChoiceGraph, ChoiceRecord } from "@/api/types";

export function ChoiceView({
  onSelectLabel,
}: {
  onSelectLabel: (name: string) => void;
}) {
  const choiceQ = useQuery({
    queryKey: ["choice-graph"],
    queryFn: () => api<ChoiceGraph>("/api/choice-graph"),
  });

  if (choiceQ.isLoading) {
    return <div className="p-8 text-sm text-ink3">Loading choice graph…</div>;
  }
  if (choiceQ.error) {
    return <div className="p-8 text-sm text-rose-600">Error: {String(choiceQ.error)}</div>;
  }
  if (!choiceQ.data || choiceQ.data.count === 0) {
    return <EmptyChoiceView />;
  }

  return (
    <div className="w-full h-full overflow-auto bg-canvas">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        <header className="border-b border-line pb-3">
          <span className="text-[10px] uppercase tracking-wide text-ink3 font-mono">
            Player perspective
          </span>
          <h1 className="font-serif text-2xl text-ink mt-1">Choice View</h1>
          <p className="text-xs text-ink3 mt-1">
            {choiceQ.data.count} menu{choiceQ.data.count === 1 ? "" : "s"} across the
            project · click a target to open it in the Inspector
          </p>
        </header>

        {choiceQ.data.choices.map((choice) => (
          <ChoiceCard
            key={`${choice.label}:${choice.line}`}
            choice={choice}
            onSelectLabel={onSelectLabel}
          />
        ))}
      </div>
    </div>
  );
}

function ChoiceCard({
  choice,
  onSelectLabel,
}: {
  choice: ChoiceRecord;
  onSelectLabel: (name: string) => void;
}) {
  return (
    <article className="bg-card border border-line rounded-lg shadow-sm overflow-hidden">
      <header className="px-4 py-2.5 border-b border-line bg-cardAlt/40 flex items-baseline justify-between">
        <button
          onClick={() => onSelectLabel(choice.label)}
          className="font-serif text-base text-ink hover:underline text-left"
          title={`Open ${choice.label} in the Inspector`}
        >
          {choice.label}
        </button>
        <span className="text-[10px] font-mono text-ink3">
          {choice.file}:{choice.line}
        </span>
      </header>
      <ul className="divide-y divide-line">
        {choice.branches.map((branch, i) => (
          <li key={i} className="px-4 py-2 flex items-start gap-3 text-sm">
            <span
              className="inline-flex items-center px-2 py-0.5 rounded-full text-xs"
              style={{
                background: "var(--rp-card-2)",
                color: "var(--rp-ink-2)",
              }}
            >
              "{branch.text}"
            </span>
            {branch.condition && (
              <span
                className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-mono"
                style={{
                  background: "var(--rp-card-2)",
                  color: "var(--rp-accent)",
                }}
                title={`if ${branch.condition}`}
              >
                if {branch.condition}
              </span>
            )}
            <ArrowRight className="w-4 h-4 text-ink3 mt-1 shrink-0" />
            {branch.target ? (
              <button
                onClick={() => onSelectLabel(branch.target!)}
                className="font-mono text-sm text-ink hover:underline"
                title={`Open ${branch.target} in the Inspector`}
              >
                {branch.target}
              </button>
            ) : (
              <span className="font-mono text-xs text-ink3 italic inline-flex items-center gap-1">
                <AlertCircle className="w-3.5 h-3.5" />
                no jump (branch has no clear target)
              </span>
            )}
            {branch.target_kind === "call" && (
              <span className="text-[10px] font-mono text-ink3 ml-auto">
                via call
              </span>
            )}
          </li>
        ))}
      </ul>
    </article>
  );
}

function EmptyChoiceView() {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center text-ink3 text-sm">
      <p className="font-serif text-base">No choices in this project yet.</p>
      <p className="text-xs mt-2">
        Add a <code className="font-mono">menu:</code> to a label and they'll show up here.
      </p>
    </div>
  );
}
