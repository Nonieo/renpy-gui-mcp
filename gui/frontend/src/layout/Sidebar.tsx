import { clsx } from "clsx";
import {
  GitBranch,
  Split,
  Users,
  Image,
  Database,
  Film,
  Gamepad2,
  Music,
  Languages as LanguagesIcon,
  Wand2,
  Hammer,
} from "lucide-react";
import type { Rail } from "@/lib/usePrefs";

export type PanelId =
  | "story"
  | "choice"
  | "characters"
  | "assets"
  | "variables"
  | "animations"
  | "minigames"
  | "music"
  | "languages"
  | "composers"
  | "build";

interface PanelMeta {
  id: PanelId;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
}

const ITEMS: PanelMeta[] = [
  { id: "story", label: "Story Map", hint: "branching graph", icon: GitBranch },
  { id: "choice", label: "Choice View", hint: "player perspective", icon: Split },
  { id: "characters", label: "Characters", hint: "cast & display names", icon: Users },
  { id: "assets", label: "Assets", hint: "bg · sprites · audio", icon: Image },
  { id: "variables", label: "Variables", hint: "default values", icon: Database },
  { id: "animations", label: "Animations", hint: "ATL stub", icon: Film },
  { id: "minigames", label: "Mini-Games", hint: "screen scaffolds", icon: Gamepad2 },
  { id: "music", label: "Music", hint: "per-scene scoring", icon: Music },
  { id: "languages", label: "Languages", hint: "translation coverage", icon: LanguagesIcon },
  { id: "composers", label: "Composers", hint: "visual generators", icon: Wand2 },
  { id: "build", label: "Build", hint: "lint & distribute", icon: Hammer },
];

export function Sidebar({
  active,
  onSelect,
  rail,
}: {
  active: PanelId;
  onSelect: (id: PanelId) => void;
  rail: Rail;
}) {
  if (rail === "palette") {
    return <PaletteRail active={active} onSelect={onSelect} />;
  }
  const showLabels = rail === "labeled";
  return (
    <nav
      className={clsx(
        "bg-rail text-railText shrink-0 flex flex-col border-r border-railLine",
        showLabels ? "w-56" : "w-14",
      )}
    >
      <Brand showLabels={showLabels} />
      <ul className="flex-1 py-2">
        {ITEMS.map(({ id, label, hint, icon: Icon }) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => onSelect(id)}
              title={!showLabels ? label : undefined}
              className={clsx(
                "w-full flex items-center gap-3 px-3 py-2 text-sm transition-colors",
                showLabels ? "px-4" : "justify-center",
                active === id
                  ? "bg-white/5 text-railText border-l-2 pl-[10px]"
                  : "text-railTextDim hover:text-railText hover:bg-white/5",
              )}
              style={
                active === id
                  ? { borderLeftColor: "var(--rp-accent)" }
                  : undefined
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              {showLabels && (
                <span className="flex flex-col items-start min-w-0">
                  <span className="leading-tight">{label}</span>
                  <span className="text-[10px] text-railTextDim font-mono leading-tight">
                    {hint}
                  </span>
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
      <Foot showLabels={showLabels} />
    </nav>
  );
}

function PaletteRail({
  active,
  onSelect,
}: {
  active: PanelId;
  onSelect: (id: PanelId) => void;
}) {
  return (
    <nav className="bg-rail text-railText w-72 shrink-0 flex flex-col border-r border-railLine">
      <div className="px-3 pt-3">
        <div className="rounded-md border border-railLine bg-white/5 px-3 py-2 flex items-center gap-2">
          <span className="font-mono text-base" style={{ color: "var(--rp-accent)" }}>
            ›
          </span>
          <span className="text-sm text-railTextDim flex-1">Go to panel…</span>
          <kbd className="text-[10px] font-mono text-railTextDim border border-railLine rounded px-1 py-0.5">
            ⌘K
          </kbd>
        </div>
      </div>
      <ul className="flex-1 py-2 space-y-0.5">
        {ITEMS.map(({ id, label, hint, icon: Icon }) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => onSelect(id)}
              className={clsx(
                "w-full grid grid-cols-[20px_1fr_auto] gap-2 items-center px-3 py-1.5 text-left text-sm transition-colors",
                active === id
                  ? "bg-white/[0.07] text-railText"
                  : "text-railTextDim hover:bg-white/[0.04] hover:text-railText",
              )}
            >
              <Icon className="w-4 h-4 row-span-2" />
              <span className="leading-tight font-medium">{label}</span>
              <span
                className="text-[10px] font-mono text-railTextDim col-start-2 leading-tight"
              >
                {hint}
              </span>
              {active === id && (
                <span
                  className="row-span-2 text-xs font-mono"
                  style={{ color: "var(--rp-accent)" }}
                >
                  ↵
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
      <Foot showLabels />
    </nav>
  );
}

function Brand({ showLabels }: { showLabels: boolean }) {
  return (
    <div
      className={clsx(
        "px-4 py-3 border-b border-railLine flex items-center gap-3",
        !showLabels && "justify-center px-2",
      )}
    >
      <div
        className="w-8 h-8 rounded-md flex items-center justify-center text-xs font-bold"
        style={{ background: "var(--rp-accent)", color: "white" }}
      >
        RP
      </div>
      {showLabels && (
        <div className="flex flex-col leading-tight min-w-0">
          <span className="font-serif text-base">RPBuilder</span>
          <span className="text-[10px] font-mono text-railTextDim">renpy-mcp · v0.1</span>
        </div>
      )}
    </div>
  );
}

function Foot({ showLabels }: { showLabels: boolean }) {
  return (
    <div className="px-3 py-3 border-t border-railLine">
      {showLabels ? (
        <div className="flex items-center gap-2 text-[10px] font-mono text-railTextDim">
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: "var(--rp-accent)" }}
          />
          file watcher · live
        </div>
      ) : (
        <div
          className="w-1.5 h-1.5 rounded-full mx-auto"
          style={{ background: "var(--rp-accent)" }}
          title="file watcher · live"
        />
      )}
    </div>
  );
}
