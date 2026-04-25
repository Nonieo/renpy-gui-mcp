import { useEffect } from "react";
import { clsx } from "clsx";
import { X } from "lucide-react";
import {
  ACCENT_OPTIONS,
  type AccentId,
  type Density,
  type Prefs,
  type Rail,
  type Theme,
} from "@/lib/usePrefs";

const THEMES: Theme[] = ["light", "cream", "dark"];
const DENSITIES: Density[] = ["compact", "regular", "roomy"];
const RAILS: { id: Rail; sub: string }[] = [
  { id: "icon", sub: "icon only" },
  { id: "labeled", sub: "labels + hints" },
  { id: "palette", sub: "command-first" },
];

export function PrefsModal({
  prefs,
  setPref,
  onClose,
}: {
  prefs: Prefs;
  setPref: <K extends keyof Prefs>(key: K, value: Prefs[K]) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-start justify-center pt-24 z-50"
      onClick={onClose}
    >
      <div
        className="bg-card text-ink w-[560px] max-w-[92vw] rounded-lg shadow-xl border border-line"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between px-6 pt-5 pb-3 border-b border-line">
          <div>
            <div className="text-xs uppercase tracking-wide text-ink3">Workspace</div>
            <h2 className="font-serif text-xl">Appearance</h2>
          </div>
          <button
            onClick={onClose}
            className="text-ink3 hover:text-ink p-1"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </header>
        <div className="px-6 py-5 space-y-5">
          <Row
            label="Theme"
            hint="Cream is gentle on long sessions; dark for night work."
          >
            <Seg
              options={THEMES}
              value={prefs.theme}
              onChange={(v) => setPref("theme", v)}
            />
          </Row>

          <Row
            label="Accent"
            hint="Used for selection, choice nodes, and primary actions."
          >
            <div className="flex flex-wrap gap-2">
              {ACCENT_OPTIONS.map((a) => (
                <button
                  key={a.id}
                  onClick={() => setPref("accent", a.id as AccentId)}
                  className={clsx(
                    "flex items-center gap-2 px-2.5 py-1.5 rounded-md border text-xs transition-colors",
                    prefs.accent === a.id
                      ? "border-ink"
                      : "border-line hover:border-ink2",
                  )}
                  title={a.label}
                >
                  <span
                    className="w-3 h-3 rounded-full"
                    style={{ background: a.value }}
                  />
                  <span className="font-mono text-ink2">{a.label}</span>
                </button>
              ))}
            </div>
          </Row>

          <Row
            label="Graph density"
            hint="Roomy reads like a script; compact fits more on screen."
          >
            <Seg
              options={DENSITIES}
              value={prefs.density}
              onChange={(v) => setPref("density", v)}
            />
          </Row>

          <Row label="Sidebar" hint="Icon-only saves space; palette is keyboard-first.">
            <div className="flex gap-2">
              {RAILS.map((r) => (
                <button
                  key={r.id}
                  onClick={() => setPref("rail", r.id)}
                  className={clsx(
                    "flex flex-col items-start px-3 py-1.5 rounded-md border text-xs transition-colors min-w-24",
                    prefs.rail === r.id
                      ? "border-ink bg-cardAlt"
                      : "border-line hover:border-ink2",
                  )}
                >
                  <span className="font-medium text-ink">{r.id}</span>
                  <span className="text-[10px] font-mono text-ink3">{r.sub}</span>
                </button>
              ))}
            </div>
          </Row>
        </div>
        <footer className="px-6 pb-5 pt-3 border-t border-line flex items-center justify-between">
          <span className="text-xs text-ink3">Saved automatically · ⎋ to close</span>
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded-md text-sm text-white"
            style={{ background: "var(--rp-accent)" }}
          >
            Done
          </button>
        </footer>
      </div>
    </div>
  );
}

function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[180px_1fr] gap-4 items-start">
      <div>
        <div className="text-sm font-medium text-ink">{label}</div>
        <div className="text-xs text-ink3 mt-0.5">{hint}</div>
      </div>
      <div>{children}</div>
    </div>
  );
}

function Seg<T extends string>({
  options,
  value,
  onChange,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex border border-line rounded-md overflow-hidden">
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={clsx(
            "px-3 py-1.5 text-xs transition-colors",
            value === opt
              ? "bg-cardAlt text-ink font-medium"
              : "text-ink2 hover:bg-cardAlt/50",
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
