import { useState } from "react";
import { Header } from "@/layout/Header";
import { Sidebar, type PanelId } from "@/layout/Sidebar";
import { useFileWatcher } from "@/api/ws";
import { StoryMap } from "@/panels/StoryMap";
import { Characters } from "@/panels/Characters";
import { Assets } from "@/panels/Assets";
import { Stub } from "@/components/Stub";

function PanelContent({ active }: { active: PanelId }) {
  switch (active) {
    case "story":
      return <StoryMap />;
    case "characters":
      return <Characters />;
    case "assets":
      return <Assets />;
    case "variables":
      return (
        <Stub
          title="Variables"
          description="Browse `default` and `define` declarations from the project. Editing lands next."
        />
      );
    case "animations":
      return (
        <Stub
          title="Animations"
          description="ATL transforms and timing — Ren'Py's animation primitives don't map cleanly to a multi-track timeline yet."
        />
      );
    case "minigames":
      return (
        <Stub
          title="Mini-Games"
          description="Use the renpy-mcp `add_minigame_screen_scaffold` tool today; a dedicated panel ships next."
        />
      );
    case "music":
      return (
        <Stub
          title="Music"
          description="Music browsing currently lives in the Assets panel — this view will gain mixer + per-scene controls."
        />
      );
    case "build":
      return (
        <Stub
          title="Build"
          description="Lint runs through `get_lint_report`; distribution build wraps the SDK launcher. Both arrive next."
        />
      );
  }
}

export default function App() {
  const [active, setActive] = useState<PanelId>("story");
  useFileWatcher();
  return (
    <div className="flex h-full">
      <Sidebar active={active} onSelect={setActive} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 min-h-0 bg-canvas">
          <PanelContent active={active} />
        </main>
      </div>
    </div>
  );
}
