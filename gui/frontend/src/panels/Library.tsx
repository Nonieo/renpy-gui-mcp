import { useState } from "react";
import { clsx } from "clsx";
import { Users, Image, Database, FileText, Gamepad2 } from "lucide-react";
import { Characters } from "@/panels/Characters";
import { Assets } from "@/panels/Assets";
import { Variables } from "@/panels/Variables";
import { Screens } from "@/panels/Screens";
import { MiniGames } from "@/panels/MiniGames";

type Tab = "characters" | "assets" | "variables" | "screens" | "minigames";

const TABS: {
  id: Tab;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
}[] = [
  { id: "characters", label: "Characters", hint: "cast & display names", icon: Users },
  { id: "assets", label: "Assets", hint: "bg · sprites · audio", icon: Image },
  { id: "variables", label: "Variables", hint: "default values", icon: Database },
  { id: "screens", label: "Screens", hint: "screen blocks · imagemaps", icon: FileText },
  { id: "minigames", label: "Mini-Games", hint: "screen scaffolds", icon: Gamepad2 },
];

export function Library() {
  const [tab, setTab] = useState<Tab>("characters");
  return (
    <div className="w-full h-full flex flex-col min-h-0">
      <div className="px-4 py-2 border-b border-line bg-card flex items-center gap-1 overflow-x-auto">
        {TABS.map(({ id, label, hint, icon: Icon }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={clsx(
              "px-3 py-1 rounded text-xs flex items-center gap-1.5 border whitespace-nowrap",
              tab === id
                ? "bg-cardAlt text-ink border-line"
                : "text-ink3 hover:text-ink border-transparent hover:bg-cardAlt/40",
            )}
          >
            <Icon className="w-3.5 h-3.5" />
            <span className="font-medium">{label}</span>
            <span className="text-[10px] font-mono text-ink3">{hint}</span>
          </button>
        ))}
      </div>
      <div className="flex-1 min-h-0">
        {tab === "characters" && <Characters />}
        {tab === "assets" && <Assets />}
        {tab === "variables" && <Variables />}
        {tab === "screens" && <Screens />}
        {tab === "minigames" && <MiniGames />}
      </div>
    </div>
  );
}
