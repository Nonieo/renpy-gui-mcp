/**
 * Composers — visual code generators (Phase 7).
 *
 * The Composers panel hosts one section per Tier 3 composer tool. The
 * Screen Layout section is the first to land; the others (Scene,
 * ImageMap, Menu) are tracked stubs until they ship.
 *
 * Each composer takes a typed JSON tree and emits a single Ren'Py
 * construct. The tree is the source of truth — agents can call the
 * tool directly with the same shape the panel posts. The panel
 * surfaces a starter template and a result pane so authors can iterate
 * visually without leaving the GUI.
 */

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Layers, Wand2, FileText, ImageIcon, GitBranch, Plus, X } from "lucide-react";
import { api } from "@/api/client";
import type { LabelInfo } from "@/api/types";

const SCREEN_LAYOUT_STARTER = `{
  "kind": "vbox",
  "props": { "xalign": 0.5, "spacing": 10 },
  "children": [
    { "kind": "text", "text": "Hello from the composer" },
    { "kind": "textbutton", "text": "Continue", "action": "Return()" }
  ]
}`;

export function Composers() {
  return (
    <div className="w-full h-full overflow-auto bg-canvas">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        <header className="border-b border-line pb-3">
          <span className="text-[10px] uppercase tracking-wide text-ink3 font-mono">
            Visual generators
          </span>
          <h1 className="font-serif text-2xl text-ink mt-1 flex items-center gap-2">
            <Wand2 className="w-5 h-5" />
            Composers
          </h1>
          <p className="text-xs text-ink3 mt-1">
            One Tier 3 tool per composer. Each accepts a typed JSON tree and
            appends the generated Ren'Py construct to your project.
          </p>
        </header>

        <ScreenLayoutComposer />
        <StageComposer />
        <ImageMapComposer />
        <MenuComposer />
      </div>
    </div>
  );
}

function ScreenLayoutComposer() {
  const [name, setName] = useState("");
  const [file, setFile] = useState("");
  const [tree, setTree] = useState(SCREEN_LAYOUT_STARTER);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<{
    summary?: string;
    file?: string;
    diff?: string;
  } | null>(null);

  const compose = useMutation({
    mutationFn: async () => {
      setError(null);
      setReport(null);
      let parsed: unknown;
      try {
        parsed = JSON.parse(tree);
      } catch (exc) {
        throw new Error(`tree JSON is invalid: ${(exc as Error).message}`);
      }
      const body: Record<string, unknown> = { name, root: parsed };
      if (file.trim()) body.file = file.trim();
      const data = await api<{
        summary?: string;
        file?: string;
        diff?: string;
        error?: string;
      }>("/api/composers/screen-layout", { method: "POST", json: body });
      if (data.error) throw new Error(data.error);
      return data;
    },
    onSuccess: (data) => setReport(data),
    onError: (err) => setError(String(err)),
  });

  const ready = name.trim().length > 0 && tree.trim().length > 0;

  return (
    <section className="bg-card border border-line rounded-lg overflow-hidden">
      <header className="px-4 py-3 border-b border-line bg-cardAlt/40 flex items-baseline gap-2">
        <FileText className="w-4 h-4 text-ink3" />
        <h2 className="font-serif text-base text-ink">Screen Layout Composer</h2>
        <span className="text-[10px] font-mono text-ink3 ml-auto">
          add_screen_layout
        </span>
      </header>
      <div className="p-4 space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <label className="block">
            <span className="text-xs text-ink3 mb-1 inline-block">Screen name</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="title_card"
              className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
            />
          </label>
          <label className="block">
            <span className="text-xs text-ink3 mb-1 inline-block">
              Target file (optional)
            </span>
            <input
              value={file}
              onChange={(e) => setFile(e.target.value)}
              placeholder="game/screens.rpy"
              className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
            />
          </label>
        </div>

        <label className="block">
          <span className="text-xs text-ink3 mb-1 inline-block">
            Widget tree (JSON)
          </span>
          <textarea
            value={tree}
            onChange={(e) => setTree(e.target.value)}
            spellCheck={false}
            rows={14}
            className="w-full px-2 py-1.5 border border-line rounded text-xs font-mono bg-card text-ink leading-relaxed"
          />
          <p className="text-[10px] font-mono text-ink3 mt-1">
            Container kinds: <code>vbox</code> · <code>hbox</code> ·{" "}
            <code>frame</code> · <code>button</code>. Leaves: <code>text</code>{" "}
            · <code>textbutton</code> · <code>spacer</code>.
          </p>
        </label>

        <div className="flex items-center gap-2">
          <button
            onClick={() => compose.mutate()}
            disabled={!ready || compose.isPending}
            className="px-3 py-1.5 rounded text-sm text-white disabled:opacity-50"
            style={{ background: "var(--rp-accent)" }}
          >
            {compose.isPending ? "Composing…" : "Compose screen"}
          </button>
          <button
            onClick={() => setTree(SCREEN_LAYOUT_STARTER)}
            className="px-3 py-1.5 rounded text-sm border border-line text-ink2 hover:bg-cardAlt"
          >
            Reset template
          </button>
        </div>

        {error && (
          <div className="border border-rose-200 bg-rose-50 rounded p-3 text-xs text-rose-700">
            {error}
          </div>
        )}

        {report && (
          <div className="border border-line rounded overflow-hidden">
            <header className="px-3 py-1.5 bg-cardAlt/40 border-b border-line flex items-center justify-between text-xs">
              <span className="font-medium text-ink">{report.summary}</span>
              {report.file && (
                <span className="font-mono text-ink3">{report.file}</span>
              )}
            </header>
            {report.diff && (
              <pre className="bg-ink text-card font-mono p-3 text-[11px] overflow-auto max-h-64 leading-relaxed">
                {report.diff}
              </pre>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// ---------- Stage Composer ----------------------------------------------------

interface SpriteRow {
  tag: string;
  expression: string;
  position: string;
}

const EMPTY_SPRITE: SpriteRow = { tag: "", expression: "", position: "" };

function StageComposer() {
  const [label, setLabel] = useState("");
  const [background, setBackground] = useState("");
  const [transition, setTransition] = useState("");
  const [sprites, setSprites] = useState<SpriteRow[]>([{ ...EMPTY_SPRITE }]);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<{
    summary?: string;
    file?: string;
    diff?: string;
  } | null>(null);

  const labelsQ = useQuery({
    queryKey: ["labels"],
    queryFn: () => api<{ labels: LabelInfo[] }>("/api/labels"),
  });

  const updateSprite = (idx: number, patch: Partial<SpriteRow>) =>
    setSprites((rows) => rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  const addSprite = () => setSprites((rows) => [...rows, { ...EMPTY_SPRITE }]);
  const removeSprite = (idx: number) =>
    setSprites((rows) => rows.filter((_, i) => i !== idx));

  const compose = useMutation({
    mutationFn: async () => {
      setError(null);
      setReport(null);
      const filteredSprites = sprites
        .filter((s) => s.tag.trim())
        .map((s) => {
          const sprite: Record<string, string> = { tag: s.tag.trim() };
          if (s.expression.trim()) sprite.expression = s.expression.trim();
          if (s.position.trim()) sprite.position = s.position.trim();
          return sprite;
        });
      const body: Record<string, unknown> = { label };
      if (background.trim()) body.background = background.trim();
      if (filteredSprites.length) body.sprites = filteredSprites;
      if (transition.trim()) body.transition = transition.trim();
      const data = await api<{
        summary?: string;
        file?: string;
        diff?: string;
        error?: string;
      }>("/api/composers/stage", { method: "POST", json: body });
      if (data.error) throw new Error(data.error);
      return data;
    },
    onSuccess: (data) => setReport(data),
    onError: (err) => setError(String(err)),
  });

  const ready = label.trim().length > 0;
  return (
    <ComposerSection
      icon={<Layers className="w-4 h-4 text-ink3" />}
      title="Stage Composer"
      toolName="add_stage"
    >
      <div className="grid grid-cols-2 gap-3">
        <FieldLabel text="Target label">
          <select
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
          >
            <option value="">— select label —</option>
            {(labelsQ.data?.labels ?? []).map((l) => (
              <option key={l.name} value={l.name}>
                {l.name}
              </option>
            ))}
          </select>
        </FieldLabel>
        <FieldLabel text="Background">
          <input
            value={background}
            onChange={(e) => setBackground(e.target.value)}
            placeholder="bg park"
            className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
          />
        </FieldLabel>
      </div>

      <FieldLabel text="Sprites">
        <div className="space-y-1.5">
          {sprites.map((s, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-1.5">
              <input
                value={s.tag}
                onChange={(e) => updateSprite(i, { tag: e.target.value })}
                placeholder="tag (eileen)"
                className="px-2 py-1 border border-line rounded text-xs font-mono bg-card text-ink"
              />
              <input
                value={s.expression}
                onChange={(e) => updateSprite(i, { expression: e.target.value })}
                placeholder="expression (happy)"
                className="px-2 py-1 border border-line rounded text-xs font-mono bg-card text-ink"
              />
              <input
                value={s.position}
                onChange={(e) => updateSprite(i, { position: e.target.value })}
                placeholder="position (left)"
                className="px-2 py-1 border border-line rounded text-xs font-mono bg-card text-ink"
              />
              <button
                onClick={() => removeSprite(i)}
                disabled={sprites.length === 1}
                className="p-1 text-ink3 hover:text-rose-600 disabled:opacity-30"
                title="Remove sprite"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          <button
            onClick={addSprite}
            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-dashed border-line text-xs text-ink3 hover:text-ink"
          >
            <Plus className="w-3 h-3" />
            sprite
          </button>
        </div>
      </FieldLabel>

      <FieldLabel text="Transition (optional)">
        <input
          value={transition}
          onChange={(e) => setTransition(e.target.value)}
          placeholder="dissolve"
          className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
        />
      </FieldLabel>

      <ComposerActions
        ready={ready}
        pending={compose.isPending}
        onCompose={() => compose.mutate()}
        onReset={() => {
          setLabel("");
          setBackground("");
          setTransition("");
          setSprites([{ ...EMPTY_SPRITE }]);
        }}
        composeLabel="Compose stage"
      />

      <ComposerOutcome error={error} report={report} />
    </ComposerSection>
  );
}

// ---------- ImageMap Composer -------------------------------------------------

interface HotspotRow {
  x: string;
  y: string;
  w: string;
  h: string;
  action: string;
}

const EMPTY_HOTSPOT: HotspotRow = { x: "0", y: "0", w: "100", h: "50", action: "" };

function ImageMapComposer() {
  const [name, setName] = useState("");
  const [ground, setGround] = useState("");
  const [hover, setHover] = useState("");
  const [file, setFile] = useState("");
  const [hotspots, setHotspots] = useState<HotspotRow[]>([{ ...EMPTY_HOTSPOT }]);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<{
    summary?: string;
    file?: string;
    diff?: string;
  } | null>(null);

  const updateHs = (idx: number, patch: Partial<HotspotRow>) =>
    setHotspots((rows) => rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  const addHs = () => setHotspots((rows) => [...rows, { ...EMPTY_HOTSPOT }]);
  const removeHs = (idx: number) =>
    setHotspots((rows) => rows.filter((_, i) => i !== idx));

  const compose = useMutation({
    mutationFn: async () => {
      setError(null);
      setReport(null);
      const cleaned = hotspots
        .filter((h) => h.action.trim())
        .map((h) => ({
          x: parseFloat(h.x) || 0,
          y: parseFloat(h.y) || 0,
          w: parseFloat(h.w) || 0,
          h: parseFloat(h.h) || 0,
          action: h.action.trim(),
        }));
      if (cleaned.length === 0) throw new Error("at least one hotspot needs an action");
      const body: Record<string, unknown> = {
        name,
        ground: ground.trim(),
        hover: hover.trim(),
        hotspots: cleaned,
      };
      if (file.trim()) body.file = file.trim();
      const data = await api<{
        summary?: string;
        file?: string;
        diff?: string;
        error?: string;
      }>("/api/composers/imagemap", { method: "POST", json: body });
      if (data.error) throw new Error(data.error);
      return data;
    },
    onSuccess: (data) => setReport(data),
    onError: (err) => setError(String(err)),
  });

  const ready = name.trim() && ground.trim() && hover.trim();
  return (
    <ComposerSection
      icon={<ImageIcon className="w-4 h-4 text-ink3" />}
      title="ImageMap Composer"
      toolName="add_imagemap"
    >
      <div className="grid grid-cols-2 gap-3">
        <FieldLabel text="Screen name">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="title_pick"
            className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
          />
        </FieldLabel>
        <FieldLabel text="Target file (optional)">
          <input
            value={file}
            onChange={(e) => setFile(e.target.value)}
            placeholder="game/screens.rpy"
            className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
          />
        </FieldLabel>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <FieldLabel text="Ground image">
          <input
            value={ground}
            onChange={(e) => setGround(e.target.value)}
            placeholder="gui/title_idle.png"
            className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
          />
        </FieldLabel>
        <FieldLabel text="Hover image">
          <input
            value={hover}
            onChange={(e) => setHover(e.target.value)}
            placeholder="gui/title_hover.png"
            className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
          />
        </FieldLabel>
      </div>

      <FieldLabel text="Hotspots (x y w h → action)">
        <div className="space-y-1.5">
          {hotspots.map((h, i) => (
            <div
              key={i}
              className="grid grid-cols-[3rem_3rem_3rem_3rem_1fr_auto] gap-1.5"
            >
              {(["x", "y", "w", "h"] as const).map((coord) => (
                <input
                  key={coord}
                  value={h[coord]}
                  onChange={(e) => updateHs(i, { [coord]: e.target.value })}
                  placeholder={coord}
                  className="px-2 py-1 border border-line rounded text-xs font-mono bg-card text-ink"
                />
              ))}
              <input
                value={h.action}
                onChange={(e) => updateHs(i, { action: e.target.value })}
                placeholder='Jump("scene")'
                className="px-2 py-1 border border-line rounded text-xs font-mono bg-card text-ink"
              />
              <button
                onClick={() => removeHs(i)}
                disabled={hotspots.length === 1}
                className="p-1 text-ink3 hover:text-rose-600 disabled:opacity-30"
                title="Remove hotspot"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          <button
            onClick={addHs}
            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-dashed border-line text-xs text-ink3 hover:text-ink"
          >
            <Plus className="w-3 h-3" />
            hotspot
          </button>
        </div>
      </FieldLabel>

      <ComposerActions
        ready={!!ready}
        pending={compose.isPending}
        onCompose={() => compose.mutate()}
        onReset={() => {
          setName("");
          setGround("");
          setHover("");
          setFile("");
          setHotspots([{ ...EMPTY_HOTSPOT }]);
        }}
        composeLabel="Compose imagemap"
      />

      <ComposerOutcome error={error} report={report} />
    </ComposerSection>
  );
}

// ---------- Menu Composer -----------------------------------------------------
//
// No new tool — this section just calls the existing `/api/labels/{name}/menu`
// endpoint (which forwards to `add_menu`). The composer panel exists to keep
// the four ROADMAP composers visually together in one place.

interface ChoiceRow {
  text: string;
  condition: string;
  body: string;
}

const EMPTY_CHOICE: ChoiceRow = { text: "", condition: "", body: "pass" };

function MenuComposer() {
  const [label, setLabel] = useState("");
  const [choices, setChoices] = useState<ChoiceRow[]>([{ ...EMPTY_CHOICE }]);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<{
    summary?: string;
    file?: string;
    diff?: string;
  } | null>(null);

  const labelsQ = useQuery({
    queryKey: ["labels"],
    queryFn: () => api<{ labels: LabelInfo[] }>("/api/labels"),
  });

  const updateChoice = (idx: number, patch: Partial<ChoiceRow>) =>
    setChoices((rows) => rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  const addChoice = () => setChoices((rows) => [...rows, { ...EMPTY_CHOICE }]);
  const removeChoice = (idx: number) =>
    setChoices((rows) => rows.filter((_, i) => i !== idx));

  const compose = useMutation({
    mutationFn: async () => {
      setError(null);
      setReport(null);
      const cleaned = choices
        .filter((c) => c.text.trim())
        .map((c) => {
          const ch: Record<string, unknown> = { text: c.text.trim() };
          if (c.condition.trim()) ch.condition = c.condition.trim();
          // body is a multi-line string; split on newlines, trim each.
          const lines = c.body
            .split("\n")
            .map((l) => l.trim())
            .filter(Boolean);
          ch.body = lines.length ? lines : ["pass"];
          return ch;
        });
      if (cleaned.length === 0) throw new Error("at least one choice needs text");
      const data = await api<{
        summary?: string;
        file?: string;
        diff?: string;
        error?: string;
      }>(`/api/labels/${encodeURIComponent(label)}/menu`, {
        method: "POST",
        json: { choices: cleaned },
      });
      if (data.error) throw new Error(data.error);
      return data;
    },
    onSuccess: (data) => setReport(data),
    onError: (err) => setError(String(err)),
  });

  const ready = label.trim().length > 0;
  return (
    <ComposerSection
      icon={<GitBranch className="w-4 h-4 text-ink3" />}
      title="Menu Composer"
      toolName="add_menu"
    >
      <FieldLabel text="Target label">
        <select
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="w-full px-2 py-1.5 border border-line rounded text-sm font-mono bg-card text-ink"
        >
          <option value="">— select label —</option>
          {(labelsQ.data?.labels ?? []).map((l) => (
            <option key={l.name} value={l.name}>
              {l.name}
            </option>
          ))}
        </select>
      </FieldLabel>

      <FieldLabel text="Choices">
        <div className="space-y-2">
          {choices.map((c, i) => (
            <div
              key={i}
              className="border border-line rounded p-2 grid grid-cols-[1fr_auto] gap-2"
            >
              <div className="space-y-1">
                <input
                  value={c.text}
                  onChange={(e) => updateChoice(i, { text: e.target.value })}
                  placeholder='Choice text (e.g. "Take the left path")'
                  className="w-full px-2 py-1 border border-line rounded text-xs bg-card text-ink"
                />
                <input
                  value={c.condition}
                  onChange={(e) => updateChoice(i, { condition: e.target.value })}
                  placeholder='if condition (optional, e.g. "trust > 0")'
                  className="w-full px-2 py-1 border border-line rounded text-xs font-mono bg-card text-ink"
                />
                <textarea
                  value={c.body}
                  onChange={(e) => updateChoice(i, { body: e.target.value })}
                  placeholder="body lines, one per line (default: pass)"
                  rows={2}
                  className="w-full px-2 py-1 border border-line rounded text-xs font-mono bg-card text-ink"
                />
              </div>
              <button
                onClick={() => removeChoice(i)}
                disabled={choices.length === 1}
                className="p-1 text-ink3 hover:text-rose-600 disabled:opacity-30 self-start"
                title="Remove choice"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
          <button
            onClick={addChoice}
            className="inline-flex items-center gap-1 px-2 py-1 rounded border border-dashed border-line text-xs text-ink3 hover:text-ink"
          >
            <Plus className="w-3 h-3" />
            choice
          </button>
        </div>
      </FieldLabel>

      <ComposerActions
        ready={ready}
        pending={compose.isPending}
        onCompose={() => compose.mutate()}
        onReset={() => {
          setLabel("");
          setChoices([{ ...EMPTY_CHOICE }]);
        }}
        composeLabel="Compose menu"
      />

      <ComposerOutcome error={error} report={report} />
    </ComposerSection>
  );
}

// ---------- shared section/action/outcome primitives -------------------------

function ComposerSection({
  icon,
  title,
  toolName,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  toolName: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-card border border-line rounded-lg overflow-hidden">
      <header className="px-4 py-3 border-b border-line bg-cardAlt/40 flex items-baseline gap-2">
        {icon}
        <h2 className="font-serif text-base text-ink">{title}</h2>
        <span className="text-[10px] font-mono text-ink3 ml-auto">{toolName}</span>
      </header>
      <div className="p-4 space-y-3">{children}</div>
    </section>
  );
}

function FieldLabel({
  text,
  children,
}: {
  text: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-xs text-ink3 mb-1 inline-block">{text}</span>
      {children}
    </label>
  );
}

function ComposerActions({
  ready,
  pending,
  onCompose,
  onReset,
  composeLabel,
}: {
  ready: boolean;
  pending: boolean;
  onCompose: () => void;
  onReset: () => void;
  composeLabel: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onCompose}
        disabled={!ready || pending}
        className="px-3 py-1.5 rounded text-sm text-white disabled:opacity-50"
        style={{ background: "var(--rp-accent)" }}
      >
        {pending ? "Composing…" : composeLabel}
      </button>
      <button
        onClick={onReset}
        className="px-3 py-1.5 rounded text-sm border border-line text-ink2 hover:bg-cardAlt"
      >
        Reset
      </button>
    </div>
  );
}

function ComposerOutcome({
  error,
  report,
}: {
  error: string | null;
  report: { summary?: string; file?: string; diff?: string } | null;
}) {
  if (!error && !report) return null;
  if (error) {
    return (
      <div className="border border-rose-200 bg-rose-50 rounded p-3 text-xs text-rose-700">
        {error}
      </div>
    );
  }
  return (
    <div className="border border-line rounded overflow-hidden">
      <header className="px-3 py-1.5 bg-cardAlt/40 border-b border-line flex items-center justify-between text-xs">
        <span className="font-medium text-ink">{report?.summary}</span>
        {report?.file && <span className="font-mono text-ink3">{report.file}</span>}
      </header>
      {report?.diff && (
        <pre className="bg-ink text-card font-mono p-3 text-[11px] overflow-auto max-h-64 leading-relaxed">
          {report.diff}
        </pre>
      )}
    </div>
  );
}
