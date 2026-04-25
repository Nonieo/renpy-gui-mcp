import { useState } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  RefreshCw,
  Terminal,
  Download,
  Wrench,
} from "lucide-react";
import { api } from "@/api/client";
import type { LintReport } from "@/lib/lint";

interface ScaffoldIssue {
  rule: string;
  severity: "error" | "warning";
  file: string | null;
  message: string;
  fix_summary: string;
}

interface RepairAction {
  rule: string;
  outcome: string;
  file?: string;
  error?: string;
}

/**
 * Ship panel — distribute + raw lint output.
 *
 * The parsed-findings UI moved to the header `LintBadge` (see Phase 3).
 * Build keeps the raw `renpy.sh lint` output for power-use diagnosis,
 * the scaffold-repair button, and the Distribute section.
 */
export function Build() {
  const [report, setReport] = useState<LintReport | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runLint = async () => {
    if (running) return;
    setRunning(true);
    setError(null);
    try {
      const data = await api<LintReport>("/api/lint");
      if (data.error) setError(data.error);
      else setReport(data);
    } catch (err) {
      setError(String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="p-8 h-full overflow-auto max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-zinc-800">Ship</h1>
      </div>

      <DistributeSection />

      <section className="mt-10 pt-6 border-t border-zinc-100">
        <header className="flex items-baseline justify-between mb-3">
          <div>
            <span className="text-[10px] uppercase tracking-wide text-zinc-400 font-mono">
              Diagnostics
            </span>
            <h2 className="font-serif text-lg text-zinc-800">Raw lint output</h2>
            <p className="text-xs text-zinc-500 mt-1">
              The summary count lives in the header. This panel keeps the raw{" "}
              <code>renpy.sh lint</code> stdout/stderr for power-use diagnosis.
            </p>
          </div>
          <button
            onClick={runLint}
            disabled={running}
            className="px-3 py-1.5 text-sm rounded-md bg-accent text-white hover:bg-indigo-600 disabled:opacity-50 inline-flex items-center gap-1.5"
          >
            <RefreshCw className={running ? "w-4 h-4 animate-spin" : "w-4 h-4"} />
            {running ? "Running…" : report ? "Re-run lint" : "Run lint"}
          </button>
        </header>

        {error && (
          <div className="border border-red-200 bg-red-50 rounded p-3 text-xs text-red-700">
            <strong>Error:</strong> {error}
          </div>
        )}

        {!report && !running && !error && (
          <div className="border border-dashed border-zinc-300 rounded-lg p-8 text-center text-zinc-500">
            <Terminal className="w-6 h-6 mx-auto mb-2 text-zinc-400" />
            <p className="text-xs">No lint run yet.</p>
          </div>
        )}

        {report && (
          <div className="border border-zinc-200 rounded text-xs overflow-hidden">
            <header className="px-3 py-1.5 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between font-mono text-zinc-500">
              <span>exit code: {report.returncode}</span>
              {report.summary && <span>{report.summary}</span>}
            </header>
            <pre className="bg-zinc-900 text-zinc-100 font-mono p-3 overflow-auto max-h-96 leading-relaxed">
              {report.stdout || "(empty stdout)"}
              {report.stderr && (
                <>
                  {"\n--- stderr ---\n"}
                  {report.stderr}
                </>
              )}
            </pre>
          </div>
        )}
      </section>
    </div>
  );
}

/**
 * Best-effort path-of-the-output-folder for the success card.
 *  - When the user passed a destination, that's the path.
 *  - Otherwise we derive it from the first artifact's parent directory
 *    so the user can see exactly where to look (typically
 *    `<project_parent>/<name>-<version>-dists/`).
 *  - Worst case (artifacts list empty), fall back to the project parent.
 */
function deriveOutputDir(report: {
  destination?: string | null;
  default_destination?: string;
  artifacts?: string[];
}): string {
  if (report.destination) return report.destination;
  const first = report.artifacts && report.artifacts[0];
  if (first) {
    const lastSlash = Math.max(first.lastIndexOf("/"), first.lastIndexOf("\\"));
    if (lastSlash > 0) return first.slice(0, lastSlash);
  }
  return report.default_destination ?? "(unknown)";
}

function DistributeSection() {
  const [targets, setTargets] = useState<Record<string, boolean>>({
    pc: true,
    mac: true,
    linux: true,
  });
  const [running, setRunning] = useState(false);
  const [destination, setDestination] = useState("");
  const [report, setReport] = useState<{
    targets: string[];
    returncode: number;
    stdout: string;
    stderr: string;
    artifacts?: string[];
    destination?: string | null;
    default_destination?: string;
    scaffold_warnings?: ScaffoldIssue[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [repairing, setRepairing] = useState(false);
  const [repairOutcome, setRepairOutcome] = useState<{
    summary: string;
    actions: RepairAction[];
  } | null>(null);

  const PLATFORMS: { id: string; label: string; hint: string }[] = [
    { id: "pc", label: "PC", hint: "Windows + Linux zip" },
    { id: "mac", label: "macOS", hint: "universal zip" },
    { id: "linux", label: "Linux", hint: "x86_64 tarball" },
    { id: "web", label: "Web", hint: "browser export" },
    { id: "steam", label: "Steam", hint: "depot bundle" },
  ];

  const selected = Object.entries(targets)
    .filter(([, on]) => on)
    .map(([id]) => id);
  const toggle = (id: string) =>
    setTargets((p) => ({ ...p, [id]: !p[id] }));

  const startBuild = async () => {
    if (!selected.length || running) return;
    setRunning(true);
    setError(null);
    setReport(null);
    setRepairOutcome(null);
    try {
      const body: Record<string, unknown> = { targets: selected };
      if (destination.trim()) body.destination = destination.trim();
      const data = await api<{
        targets?: string[];
        returncode?: number;
        stdout?: string;
        stderr?: string;
        artifacts?: string[];
        destination?: string | null;
        default_destination?: string;
        scaffold_warnings?: ScaffoldIssue[];
        error?: string;
      }>("/api/build/distribute", { method: "POST", json: body });
      if (data.error) {
        setError(data.error);
      } else {
        setReport({
          targets: data.targets ?? [],
          returncode: data.returncode ?? -1,
          stdout: data.stdout ?? "",
          stderr: data.stderr ?? "",
          artifacts: data.artifacts ?? [],
          destination: data.destination ?? null,
          default_destination: data.default_destination,
          scaffold_warnings: data.scaffold_warnings ?? [],
        });
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setRunning(false);
    }
  };

  const runRepair = async () => {
    if (repairing) return;
    setRepairing(true);
    setRepairOutcome(null);
    try {
      const data = await api<{
        summary?: string;
        actions?: RepairAction[];
        issues?: ScaffoldIssue[];
        error?: string;
      }>("/api/scaffold/repair", { method: "POST" });
      if (data.error) {
        setError(data.error);
      } else {
        setRepairOutcome({
          summary: data.summary ?? "(no summary)",
          actions: data.actions ?? [],
        });
        setReport((prev) =>
          prev ? { ...prev, scaffold_warnings: [] } : prev
        );
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setRepairing(false);
    }
  };

  return (
    <section>
      <header className="flex items-baseline justify-between mb-3">
        <div>
          <span className="text-[10px] uppercase tracking-wide text-zinc-400 font-mono">
            Distribute
          </span>
          <h2 className="font-serif text-lg text-zinc-800">Compile for…</h2>
        </div>
        <button
          onClick={startBuild}
          disabled={!selected.length || running}
          className="px-3 py-1.5 text-sm rounded-md bg-accent text-white disabled:opacity-50 inline-flex items-center gap-1.5"
        >
          <Download className={running ? "w-4 h-4 animate-spin" : "w-4 h-4"} />
          {running ? "Compiling…" : "Build distribution"}
        </button>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
        {PLATFORMS.map((p) => {
          const on = !!targets[p.id];
          return (
            <button
              key={p.id}
              onClick={() => toggle(p.id)}
              aria-pressed={on}
              className={[
                "flex flex-col items-start gap-0.5 px-3 py-2 rounded border text-left text-sm transition-colors",
                on
                  ? "border-zinc-800 bg-zinc-50"
                  : "border-zinc-200 hover:border-zinc-400 text-zinc-500",
              ].join(" ")}
            >
              <span className="font-medium text-zinc-800">{p.label}</span>
              <span className="text-[10px] font-mono text-zinc-400">{p.hint}</span>
            </button>
          );
        })}
      </div>

      <label className="block mb-3">
        <span className="text-xs text-zinc-500 mb-1 inline-block">
          Output directory <span className="text-zinc-400">(optional)</span>
        </span>
        <input
          type="text"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          placeholder="leave empty to put artifacts next to the project folder"
          className="w-full px-2 py-1.5 border border-zinc-200 rounded text-xs font-mono bg-white text-zinc-800"
        />
        <span className="text-[10px] font-mono text-zinc-400 mt-1 inline-block">
          Default: <code>&lt;project_parent&gt;/&lt;name&gt;-&lt;version&gt;-dists/</code>
        </span>
      </label>

      <p className="text-xs text-zinc-500 mb-3">
        {selected.length === 0
          ? "Select at least one target."
          : `${selected.length} target${selected.length === 1 ? "" : "s"} → renpy.sh distribute ${selected
              .map((t) => `--package ${t}`)
              .join(" ")}${destination.trim() ? ` --destination ${destination.trim()}` : ""}`}
      </p>

      {error && (
        <div className="border border-red-200 bg-red-50 rounded p-3 text-xs text-red-700 mb-3">
          <strong>Error:</strong> {error}
        </div>
      )}

      {report && (
        <div className="space-y-3">
          {report.scaffold_warnings && report.scaffold_warnings.length > 0 && (
            <ScaffoldWarningsCard
              warnings={report.scaffold_warnings}
              onRepair={runRepair}
              repairing={repairing}
            />
          )}
          {repairOutcome && <RepairOutcomeCard outcome={repairOutcome} />}
          {report.artifacts && report.artifacts.length > 0 && (
            <div className="border border-emerald-200 bg-emerald-50 rounded p-3 text-xs">
              <div className="mb-1.5">
                <strong className="text-emerald-800 block">
                  {report.artifacts.length} artifact
                  {report.artifacts.length === 1 ? "" : "s"} produced
                </strong>
                <span className="font-mono text-emerald-700 text-[11px]">
                  in <code>{deriveOutputDir(report)}</code>
                </span>
              </div>
              <ul className="space-y-0.5">
                {report.artifacts.map((path) => {
                  const filename = path.split("/").pop() ?? path;
                  return (
                    <li key={path} className="font-mono text-emerald-700">
                      <span className="text-emerald-500">▸</span> {filename}
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
          {report.artifacts && report.artifacts.length === 0 && report.returncode === 0 && (
            <div className="border border-amber-200 bg-amber-50 rounded p-3 text-xs text-amber-800">
              renpy.sh exited 0 but no artifacts were found. Check the build
              log below — the package name(s) may not be defined in this
              project's <code>options.rpy</code>.
            </div>
          )}
          <div className="border border-zinc-200 rounded text-xs overflow-hidden">
            <header className="px-3 py-1.5 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between font-mono text-zinc-500">
              <span>
                exit code: {report.returncode} ·{" "}
                {report.targets.join(", ") || "(no targets)"}
              </span>
            </header>
            <pre className="bg-zinc-900 text-zinc-100 font-mono p-3 overflow-auto max-h-72 leading-relaxed">
              {report.stdout || "(empty stdout)"}
              {report.stderr && (
                <>
                  {"\n--- stderr ---\n"}
                  {report.stderr}
                </>
              )}
            </pre>
          </div>
        </div>
      )}
    </section>
  );
}

function ScaffoldWarningsCard({
  warnings,
  onRepair,
  repairing,
}: {
  warnings: ScaffoldIssue[];
  onRepair: () => void;
  repairing: boolean;
}) {
  return (
    <div className="border border-amber-300 bg-amber-50 rounded p-3 text-xs">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-start gap-2 min-w-0">
          <AlertTriangle className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
          <div className="min-w-0">
            <strong className="text-amber-900 block">
              {warnings.length} scaffold warning
              {warnings.length === 1 ? "" : "s"}
            </strong>
            <span className="text-amber-700">
              These template leftovers can pass lint but break the built
              game at startup.
            </span>
          </div>
        </div>
        <button
          onClick={onRepair}
          disabled={repairing}
          className="px-2.5 py-1 rounded bg-amber-700 text-white text-xs disabled:opacity-50 inline-flex items-center gap-1.5 flex-shrink-0"
        >
          <Wrench className={repairing ? "w-3.5 h-3.5 animate-spin" : "w-3.5 h-3.5"} />
          {repairing ? "Repairing…" : "Repair scaffold"}
        </button>
      </div>
      <ul className="space-y-1.5 ml-6">
        {warnings.map((w) => (
          <li key={w.rule}>
            <div className="font-mono text-amber-800">
              {w.rule}
              {w.file && <span className="text-amber-600"> · {w.file}</span>}
            </div>
            <div className="text-amber-900">{w.message}</div>
            <div className="text-amber-700 italic">Fix: {w.fix_summary}</div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RepairOutcomeCard({
  outcome,
}: {
  outcome: { summary: string; actions: RepairAction[] };
}) {
  const hasErrors = outcome.actions.some((a) => a.outcome === "error");
  const cls = hasErrors
    ? "border-red-200 bg-red-50 text-red-800"
    : "border-emerald-200 bg-emerald-50 text-emerald-800";
  return (
    <div className={`border rounded p-3 text-xs ${cls}`}>
      <div className="flex items-start gap-2 mb-1.5">
        {hasErrors ? (
          <AlertOctagon className="w-4 h-4 flex-shrink-0 mt-0.5" />
        ) : (
          <CheckCircle2 className="w-4 h-4 flex-shrink-0 mt-0.5" />
        )}
        <strong>{outcome.summary}</strong>
      </div>
      {outcome.actions.length > 0 && (
        <ul className="ml-6 space-y-0.5 font-mono">
          {outcome.actions.map((a, i) => (
            <li key={i}>
              <span className="opacity-60">{a.outcome}</span> · {a.rule}
              {a.file && <span className="opacity-60"> · {a.file}</span>}
              {a.error && <span className="text-red-700"> — {a.error}</span>}
            </li>
          ))}
        </ul>
      )}
      {!hasErrors && outcome.actions.length > 0 && (
        <p className="mt-2 ml-6 not-italic">
          Re-run the build to produce a clean artifact.
        </p>
      )}
    </div>
  );
}
