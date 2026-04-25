import { useEffect, useState } from "react";
import { Header } from "@/layout/Header";
import { Sidebar, type PanelId } from "@/layout/Sidebar";
import { PrefsModal } from "@/layout/PrefsModal";
import { CommandPalette } from "@/layout/CommandPalette";
import { useFileWatcher } from "@/api/ws";
import { usePrefs } from "@/lib/usePrefs";
import { StoryMap } from "@/panels/StoryMap";
import { ChoiceView } from "@/panels/ChoiceView";
import { Characters } from "@/panels/Characters";
import { Assets } from "@/panels/Assets";
import { Variables } from "@/panels/Variables";
import { MiniGames } from "@/panels/MiniGames";
import { Music } from "@/panels/Music";
import { Languages } from "@/panels/Languages";
import { Composers } from "@/panels/Composers";
import { Build } from "@/panels/Build";
import { SceneInspector } from "@/panels/SceneInspector";
import { Stub } from "@/components/Stub";

export default function App() {
  const [active, setActive] = useState<PanelId>("story");
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { prefs, setPref } = usePrefs();
  useFileWatcher();

  // Closing the inspector when leaving Story Map keeps state predictable.
  // Choice View also opens the inspector, so we keep `selectedLabel` alive
  // across the story↔choice boundary.
  const setActivePanel = (id: PanelId) => {
    if (id !== "story" && id !== "choice") setSelectedLabel(null);
    setActive(id);
  };

  // Choice View → label click jumps to Story Map so the inspector + canvas
  // both reflect the selection.
  const openLabelFromChoice = (name: string) => {
    setActive("story");
    setSelectedLabel(name);
  };

  // Global ⌘K / Ctrl+K opens the command palette.
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="flex h-full">
      <Sidebar active={active} onSelect={setActivePanel} rail={prefs.rail} />
      <div className="flex-1 flex flex-col min-w-0">
        <Header onOpenPrefs={() => setPrefsOpen(true)} />
        <main className="flex-1 min-h-0 bg-canvas flex">
          <div className="flex-1 min-w-0">
            {active === "story" && (
              <StoryMap selectedLabel={selectedLabel} onSelectLabel={setSelectedLabel} />
            )}
            {active === "choice" && (
              <ChoiceView onSelectLabel={openLabelFromChoice} />
            )}
            {active === "characters" && <Characters />}
            {active === "assets" && <Assets />}
            {active === "variables" && <Variables />}
            {active === "animations" && (
              <Stub
                title="Animations"
                description="ATL transforms and timing — Ren'Py's animation primitives don't map cleanly to a multi-track timeline yet."
              />
            )}
            {active === "minigames" && <MiniGames />}
            {active === "music" && <Music />}
            {active === "languages" && <Languages />}
            {active === "composers" && <Composers />}
            {active === "build" && <Build />}
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

      {prefsOpen && (
        <PrefsModal
          prefs={prefs}
          setPref={setPref}
          onClose={() => setPrefsOpen(false)}
        />
      )}
      {paletteOpen && (
        <CommandPalette
          onClose={() => setPaletteOpen(false)}
          onSelectPanel={(id) => {
            setActivePanel(id);
            setPaletteOpen(false);
          }}
          onSelectLabel={(name) => {
            setActivePanel("story");
            setSelectedLabel(name);
            setPaletteOpen(false);
          }}
        />
      )}
    </div>
  );
}
