import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
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
  FileText,
} from "lucide-react";
import { api } from "@/api/client";
import type { LabelInfo } from "@/api/types";
import type { PanelId } from "@/layout/Sidebar";

interface PanelEntry {
  kind: "panel";
  id: PanelId;
  label: string;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface LabelEntry {
  kind: "label";
  name: string;
  file: string;
}

type Entry = PanelEntry | LabelEntry;

const PANEL_ENTRIES: PanelEntry[] = [
  { kind: "panel", id: "story", label: "Story Map", hint: "branching graph", icon: GitBranch },
  { kind: "panel", id: "choice", label: "Choice View", hint: "player perspective", icon: Split },
  { kind: "panel", id: "characters", label: "Characters", hint: "cast & display names", icon: Users },
  { kind: "panel", id: "assets", label: "Assets", hint: "bg · sprites · audio", icon: Image },
  { kind: "panel", id: "variables", label: "Variables", hint: "default values", icon: Database },
  { kind: "panel", id: "animations", label: "Animations", hint: "ATL stub", icon: Film },
  { kind: "panel", id: "minigames", label: "Mini-Games", hint: "screen scaffolds", icon: Gamepad2 },
  { kind: "panel", id: "music", label: "Music", hint: "per-scene scoring", icon: Music },
  { kind: "panel", id: "languages", label: "Languages", hint: "translation coverage", icon: LanguagesIcon },
  { kind: "panel", id: "composers", label: "Composers", hint: "visual generators", icon: Wand2 },
  { kind: "panel", id: "build", label: "Build", hint: "lint & distribute", icon: Hammer },
];

export function CommandPalette({
  onClose,
  onSelectPanel,
  onSelectLabel,
}: {
  onClose: () => void;
  onSelectPanel: (id: PanelId) => void;
  onSelectLabel: (name: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);

  const labelsQ = useQuery({
    queryKey: ["labels"],
    queryFn: () => api<{ labels: LabelInfo[] }>("/api/labels"),
  });

  const entries = useMemo<Entry[]>(() => {
    const labelEntries: LabelEntry[] = (labelsQ.data?.labels ?? []).map((l) => ({
      kind: "label",
      name: l.name,
      file: l.file,
    }));
    const all: Entry[] = [...PANEL_ENTRIES, ...labelEntries];
    const q = query.trim().toLowerCase();
    if (!q) return all;
    return all.filter((e) => {
      if (e.kind === "panel") {
        return (
          e.label.toLowerCase().includes(q) ||
          e.id.toLowerCase().includes(q) ||
          e.hint.toLowerCase().includes(q)
        );
      }
      return e.name.toLowerCase().includes(q) || e.file.toLowerCase().includes(q);
    });
  }, [labelsQ.data, query]);

  // Keep cursor in range as the filtered list shrinks/grows.
  useEffect(() => {
    if (cursor >= entries.length) setCursor(Math.max(0, entries.length - 1));
  }, [entries.length, cursor]);

  // Auto-focus input on mount.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Keyboard nav.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setCursor((c) => Math.min(entries.length - 1, c + 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setCursor((c) => Math.max(0, c - 1));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const entry = entries[cursor];
        if (!entry) return;
        if (entry.kind === "panel") onSelectPanel(entry.id);
        else onSelectLabel(entry.name);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [entries, cursor, onClose, onSelectPanel, onSelectLabel]);

  // Scroll the highlighted item into view as the cursor moves.
  useEffect(() => {
    const node = listRef.current?.children[cursor] as HTMLElement | undefined;
    node?.scrollIntoView({ block: "nearest" });
  }, [cursor]);

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-start justify-center pt-24 z-50"
      onClick={onClose}
    >
      <div
        className="bg-card text-ink w-[560px] max-w-[92vw] rounded-lg shadow-xl border border-line overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
          <span
            className="font-mono text-base"
            style={{ color: "var(--rp-accent)" }}
          >
            ›
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setCursor(0);
            }}
            placeholder="Jump to panel or label…"
            className="flex-1 bg-transparent outline-none text-sm text-ink placeholder:text-ink3"
          />
          <kbd className="text-[10px] font-mono text-ink3 border border-line rounded px-1 py-0.5">
            esc
          </kbd>
        </div>
        <ul ref={listRef} className="max-h-80 overflow-y-auto py-1">
          {entries.length === 0 && (
            <li className="px-4 py-6 text-center text-xs text-ink3">no matches</li>
          )}
          {entries.map((entry, idx) => (
            <li
              key={entry.kind === "panel" ? `p:${entry.id}` : `l:${entry.name}`}
              onMouseEnter={() => setCursor(idx)}
              onClick={() => {
                if (entry.kind === "panel") onSelectPanel(entry.id);
                else onSelectLabel(entry.name);
              }}
              className={clsx(
                "grid grid-cols-[20px_1fr_auto] gap-3 items-center px-4 py-2 cursor-pointer",
                idx === cursor ? "bg-cardAlt" : "hover:bg-cardAlt/50",
              )}
            >
              {entry.kind === "panel" ? (
                <entry.icon className="w-4 h-4 text-ink3" />
              ) : (
                <FileText className="w-4 h-4 text-ink3" />
              )}
              <div className="min-w-0">
                <div className="text-sm text-ink truncate">
                  {entry.kind === "panel" ? entry.label : entry.name}
                </div>
                <div className="text-[11px] font-mono text-ink3 truncate">
                  {entry.kind === "panel" ? entry.hint : entry.file}
                </div>
              </div>
              {idx === cursor && (
                <kbd
                  className="text-[10px] font-mono"
                  style={{ color: "var(--rp-accent)" }}
                >
                  ↵
                </kbd>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
