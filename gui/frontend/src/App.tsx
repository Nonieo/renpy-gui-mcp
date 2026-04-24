import { useState } from "react";
import { Header } from "@/layout/Header";
import { Sidebar, type PanelId } from "@/layout/Sidebar";
import { useFileWatcher } from "@/api/ws";
import { StoryMap } from "@/panels/StoryMap";
import { Characters } from "@/panels/Characters";
import { Assets } from "@/panels/Assets";
import { SceneInspector } from "@/panels/SceneInspector";
import { Stub } from "@/components/Stub";

export default function App() {
  const [active, setActive] = useState<PanelId>("story");
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  useFileWatcher();

  // Closing the inspector when leaving the Story Map keeps state predictable.
  const setActivePanel = (id: PanelId) => {
    if (id !== "story") setSelectedLabel(null);
    setActive(id);
  };

  return (
    <div className="flex h-full">
      <Sidebar active={active} onSelect={setActivePanel} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 min-h-0 bg-canvas flex">
          <div className="flex-1 min-w-0">
            {active === "story" && (
              <StoryMap selectedLabel={selectedLabel} onSelectLabel={setSelectedLabel} />
            )}
            {active === "characters" && <Characters />}
            {active === "assets" && <Assets />}
            {active === "variables" && (
              <Stub
                title="Variables"
                description="Browse `default` and `define` declarations from the project. Editing lands next."
              />
            )}
            {active === "animations" && (
              <Stub
                title="Animations"
                description="ATL transforms and timing — Ren'Py's animation primitives don't map cleanly to a multi-track timeline yet."
              />
            )}
            {active === "minigames" && (
              <Stub
                title="Mini-Games"
                description="Use the renpy-mcp `add_minigame_screen_scaffold` tool today; a dedicated panel ships next."
              />
            )}
            {active === "music" && (
              <Stub
                title="Music"
                description="Music browsing currently lives in the Assets panel — this view will gain mixer + per-scene controls."
              />
            )}
            {active === "build" && (
              <Stub
                title="Build"
                description="Lint runs through `get_lint_report`; distribution build wraps the SDK launcher. Both arrive next."
              />
            )}
          </div>
          {active === "story" && selectedLabel && (
            <SceneInspector
              key={selectedLabel}
              name={selectedLabel}
              onClose={() => setSelectedLabel(null)}
            />
          )}
        </main>
      </div>
    </div>
  );
}
