import { clsx } from "clsx";
import {
  GitBranch,
  Users,
  Image,
  Database,
  Film,
  Gamepad2,
  Music,
  Hammer,
} from "lucide-react";

export type PanelId =
  | "story"
  | "characters"
  | "assets"
  | "variables"
  | "animations"
  | "minigames"
  | "music"
  | "build";

const ITEMS: { id: PanelId; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: "story", label: "Story Map", icon: GitBranch },
  { id: "characters", label: "Characters", icon: Users },
  { id: "assets", label: "Assets", icon: Image },
  { id: "variables", label: "Variables", icon: Database },
  { id: "animations", label: "Animations", icon: Film },
  { id: "minigames", label: "Mini-Games", icon: Gamepad2 },
  { id: "music", label: "Music", icon: Music },
  { id: "build", label: "Build", icon: Hammer },
];

export function Sidebar({
  active,
  onSelect,
}: {
  active: PanelId;
  onSelect: (id: PanelId) => void;
}) {
  return (
    <nav className="bg-rail text-railText w-56 shrink-0 flex flex-col">
      <div className="px-4 py-4 text-lg font-semibold border-b border-zinc-800">
        <span className="text-accent">RP</span>Builder
      </div>
      <ul className="flex-1 py-2">
        {ITEMS.map(({ id, label, icon: Icon }) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => onSelect(id)}
              className={clsx(
                "w-full flex items-center gap-3 px-4 py-2 text-sm transition-colors",
                active === id
                  ? "bg-zinc-800 text-white border-l-2 border-accent pl-[14px]"
                  : "text-zinc-400 hover:text-white hover:bg-zinc-800/60",
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          </li>
        ))}
      </ul>
      <div className="px-4 py-3 text-xs text-zinc-500 border-t border-zinc-800">
        renpy-mcp v0.1
      </div>
    </nav>
  );
}
