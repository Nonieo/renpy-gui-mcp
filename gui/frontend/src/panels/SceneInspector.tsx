/**
 * Scene Inspector — Phase 4 rewrite.
 *
 * Consumes `/api/labels/{name}/tree` (Phase 0's `read_label_tree` over
 * REST) instead of parsing raw `.rpy` source on the client. The body is
 * rendered as an ordered event stream — every Ren'Py construct the
 * server's parser knows about (say, scene, show, hide, play, stop,
 * pause, jump, call, return, with, set, menu, if) gets its own card.
 *
 * Editing surface:
 *   - Background / music / dialogue keep their existing edit forms at
 *     the top (they pre-date Phase 4 and are still wired to the old
 *     tools that work fine).
 *   - "+ Insert event" at the bottom opens a popup of the five new
 *     event tools (pause, setvar, show, with, flash) — each with a
 *     small inline form that calls the matching REST endpoint.
 *
 * In-place editing of existing events lands when each event type gets
 * a corresponding line-precise edit tool (parallel to `redirect_jump`).
 * For now, events are read-only after they're authored.
 */

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronRight,
  Image,
  MessageSquare,
  Music,
  Plus,
  Timer,
  Variable,
  Wand2,
  X,
  Zap,
} from "lucide-react";
import { api } from "@/api/client";
import type {
  CharacterInfo,
  LabelTree,
  LabelTreeNode,
} from "@/api/types";

interface InspectorProps {
  name: string;
  onClose: () => void;
}

export function SceneInspector({ name, onClose }: InspectorProps) {
  const treeQ = useQuery({
    queryKey: ["label-tree", name],
    queryFn: () => api<LabelTree>(`/api/labels/${encodeURIComponent(name)}/tree`),
  });
  const charactersQ = useQuery({
    queryKey: ["characters"],
    queryFn: () => api<{ characters: CharacterInfo[] }>("/api/characters"),
  });

  return (
    <aside className="w-96 shrink-0 border-l border-line bg-card flex flex-col">
      <header className="px-5 py-3 border-b border-line flex items-center justify-between">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wide text-ink3">
            {treeQ.data ? treeQ.data.kind : "Scene"}
          </div>
          <h2 className="font-serif text-base truncate">{name}</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-ink3 hover:text-ink"
          title="Close inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </header>

      <div className="flex-1 overflow-auto px-5 py-4 space-y-5 text-sm">
        {treeQ.isLoading && <p className="text-ink3">Loading scene…</p>}
        {treeQ.error && (
          <p className="text-rose-600">Error: {String(treeQ.error)}</p>
        )}

        {treeQ.data && (
          <>
            <Section icon={<Image className="w-4 h-4" />} title="Background">
              <BackgroundField labelName={name} current={treeQ.data.shorthand.background} />
            </Section>

            <Section icon={<Music className="w-4 h-4" />} title="Music">
              <MusicField labelName={name} current={treeQ.data.shorthand.music} />
            </Section>

            <Section
              icon={<ChevronRight className="w-4 h-4" />}
              title={`Outgoing (${treeQ.data.shorthand.outgoing_targets.length})`}
            >
              {treeQ.data.shorthand.outgoing_targets.length === 0 ? (
                <p className="text-ink3 text-xs">
                  {treeQ.data.shorthand.ends_with_return
                    ? "Ends with `return`."
                    : "No outgoing jumps."}
                </p>
              ) : (
                <ul className="space-y-1 text-xs font-mono text-ink2">
                  {treeQ.data.shorthand.outgoing_targets.map((t) => (
                    <li key={t}>→ {t}</li>
                  ))}
                </ul>
              )}
            </Section>

            <Section
              icon={<MessageSquare className="w-4 h-4" />}
              title={`Body (${treeQ.data.body.length})`}
            >
              <EventStream nodes={treeQ.data.body} />
              <AddDialogueForm
                labelName={name}
                characters={charactersQ.data?.characters ?? []}
              />
              <InsertEvent labelName={name} />
            </Section>

            {treeQ.data.unparsed.length > 0 && (
              <Section
                icon={<AlertTriangle className="w-4 h-4 text-amber-500" />}
                title={`Unparsed (${treeQ.data.unparsed.length})`}
              >
                <p className="text-xs text-ink3 mb-2">
                  These lines weren't recognized by the parser. Edit with the
                  renpy-mcp tools or a text editor — the GUI will not
                  modify them.
                </p>
                <ul className="space-y-1 font-mono text-[11px] text-ink3">
                  {treeQ.data.unparsed.map((u) => (
                    <li key={u.line}>
                      <span className="text-ink3/60">{u.line}:</span> {u.raw}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <div className="text-[10px] text-ink3 font-mono pt-2 border-t border-line">
              {treeQ.data.label.file}:{treeQ.data.label.start_line}–
              {treeQ.data.label.end_line}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink3 mb-2">
        {icon}
        {title}
      </h3>
      <div className="pl-1">{children}</div>
    </section>
  );
}

// ---------- existing edit forms (background / music / dialogue) -------------

function MusicField({ labelName, current }: { labelName: string; current: string | null }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState(current ?? "");
  const [loop, setLoop] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dirty = draft.trim() !== (current ?? "").trim();

  const setMusic = useMutation({
    mutationFn: () =>
      api<{ summary?: string; error?: string }>(
        `/api/labels/${encodeURIComponent(labelName)}/music`,
        {
          method: "POST",
          json: { asset: draft.trim(), loop, validate_asset: draft.trim() !== "" },
        },
      ),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error);
        return;
      }
      qc.invalidateQueries({ queryKey: ["label-tree", labelName] });
      qc.invalidateQueries({ queryKey: ["audio"] });
    },
    onError: (err) => setError(String(err)),
  });

  return (
    <div className="space-y-1.5">
      <input
        type="text"
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          setError(null);
        }}
        placeholder="audio/spring_theme.ogg (or empty for stop music)"
        className="w-full px-2 py-1.5 border border-line rounded text-xs font-mono bg-card text-ink"
      />
      <label className="flex items-center gap-1.5 text-xs text-ink2">
        <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} />
        loop
      </label>
      {error && <div className="text-xs text-rose-600">{error}</div>}
      {dirty && (
        <button
          onClick={() => setMusic.mutate()}
          disabled={setMusic.isPending}
          className="px-2 py-1 text-xs rounded text-white disabled:opacity-50"
          style={{ background: "var(--rp-accent)" }}
        >
          {setMusic.isPending
            ? "Saving…"
            : draft.trim() === ""
              ? "Stop music"
              : "Set music"}
        </button>
      )}
    </div>
  );
}

function BackgroundField({ labelName, current }: { labelName: string; current: string | null }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState(current ?? "");
  const [error, setError] = useState<string | null>(null);
  const dirty = draft.trim() !== (current ?? "").trim();

  const swap = useMutation({
    mutationFn: () =>
      api<{ summary?: string; error?: string }>(
        `/api/labels/${encodeURIComponent(labelName)}/background`,
        { method: "POST", json: { new_background: draft.trim() } },
      ),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error);
        return;
      }
      qc.invalidateQueries({ queryKey: ["label-tree", labelName] });
      qc.invalidateQueries({ queryKey: ["graph"] });
    },
    onError: (err) => setError(String(err)),
  });

  if (current === null && !dirty) {
    return (
      <p className="text-xs text-ink3">
        No `scene` line — this label doesn't set a background. Edit via tools
        for now.
      </p>
    );
  }
  return (
    <div className="space-y-1.5">
      <input
        type="text"
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          setError(null);
        }}
        placeholder="bg park"
        className="w-full px-2 py-1.5 border border-line rounded text-xs font-mono bg-card text-ink"
      />
      {error && <div className="text-xs text-rose-600">{error}</div>}
      {dirty && (
        <button
          onClick={() => swap.mutate()}
          disabled={swap.isPending}
          className="px-2 py-1 text-xs rounded text-white disabled:opacity-50"
          style={{ background: "var(--rp-accent)" }}
        >
          {swap.isPending ? "Saving…" : "Swap background"}
        </button>
      )}
    </div>
  );
}

function AddDialogueForm({
  labelName,
  characters,
}: {
  labelName: string;
  characters: CharacterInfo[];
}) {
  const qc = useQueryClient();
  const [character, setCharacter] = useState<string>("");
  const [text, setText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const append = useMutation({
    mutationFn: () =>
      api<{ summary?: string; error?: string }>(
        `/api/labels/${encodeURIComponent(labelName)}/dialogue`,
        { method: "POST", json: { character: character || null, text } },
      ),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error);
        return;
      }
      setText("");
      qc.invalidateQueries({ queryKey: ["label-tree", labelName] });
      qc.invalidateQueries({ queryKey: ["graph"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (err) => setError(String(err)),
  });

  return (
    <div className="space-y-1.5 border-t border-line pt-3 mb-3">
      <div className="flex gap-1.5">
        <select
          value={character}
          onChange={(e) => setCharacter(e.target.value)}
          className="px-2 py-1.5 border border-line rounded text-xs font-mono w-24 bg-card text-ink"
        >
          <option value="">(narration)</option>
          {characters.map((c) => (
            <option key={c.var} value={c.var}>
              {c.var}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setError(null);
          }}
          placeholder="Add a dialogue line…"
          className="flex-1 px-2 py-1.5 border border-line rounded text-xs bg-card text-ink"
          onKeyDown={(e) => {
            if (e.key === "Enter" && text.trim() && !append.isPending) append.mutate();
          }}
        />
      </div>
      {error && <div className="text-xs text-rose-600">{error}</div>}
      <button
        onClick={() => append.mutate()}
        disabled={!text.trim() || append.isPending}
        className="px-2 py-1 text-xs rounded text-white disabled:opacity-40 inline-flex items-center gap-1"
        style={{ background: "var(--rp-ink)" }}
      >
        <Plus className="w-3 h-3" /> {append.isPending ? "Adding…" : "Add line"}
      </button>
    </div>
  );
}

// ---------- event stream rendering ------------------------------------------

function EventStream({ nodes }: { nodes: LabelTreeNode[] }) {
  if (nodes.length === 0) {
    return <p className="text-xs text-ink3">No body yet.</p>;
  }
  return (
    <ol className="space-y-1.5 mb-3">
      {nodes.map((n, i) => (
        <EventCard key={i} node={n} />
      ))}
    </ol>
  );
}

function EventCard({ node }: { node: LabelTreeNode }) {
  return (
    <li className="rounded-md border border-line bg-card/60 px-2.5 py-1.5">
      <div className="flex items-baseline gap-2 text-xs">
        <KindBadge kind={node.kind} />
        <EventBody node={node} />
        <span className="ml-auto text-[10px] font-mono text-ink3">
          L{node.line}
        </span>
      </div>
    </li>
  );
}

function KindBadge({ kind }: { kind: LabelTreeNode["kind"] }) {
  const labels: Record<LabelTreeNode["kind"], string> = {
    say: "say",
    scene: "scene",
    show: "show",
    hide: "hide",
    play: "play",
    stop: "stop",
    pause: "pause",
    jump: "jump",
    call: "call",
    return: "return",
    with: "with",
    set: "$",
    menu: "menu",
    if: "if",
  };
  return (
    <span
      className="text-[10px] font-mono uppercase tracking-wide rounded px-1.5 py-0.5 bg-cardAlt text-ink2"
      style={{ minWidth: 36, textAlign: "center", display: "inline-block" }}
    >
      {labels[kind]}
    </span>
  );
}

function EventBody({ node }: { node: LabelTreeNode }) {
  switch (node.kind) {
    case "say":
      return (
        <span className="text-ink2">
          {node.character ? (
            <span className="font-mono font-semibold text-ink">{node.character} </span>
          ) : (
            <span className="font-mono italic text-ink3">narration </span>
          )}
          <span className="text-ink2">"{node.text}"</span>
        </span>
      );
    case "scene":
    case "show":
    case "hide":
      return <span className="font-mono text-ink2">{node.expression}</span>;
    case "play":
      return (
        <span className="font-mono text-ink2">
          {node.channel} "{node.asset}"{node.options ? ` ${node.options}` : ""}
        </span>
      );
    case "stop":
      return (
        <span className="font-mono text-ink2">
          {node.channel}
          {node.options ? ` ${node.options}` : ""}
        </span>
      );
    case "pause":
      return <span className="font-mono text-ink2">{node.duration ?? "(no arg)"}</span>;
    case "jump":
      return <span className="font-mono text-ink2">{node.target}</span>;
    case "call":
      return (
        <span className="font-mono text-ink2">
          {node.target}
          {node.rest ? ` ${node.rest}` : ""}
        </span>
      );
    case "return":
      return null;
    case "with":
    case "set":
      return <span className="font-mono text-ink2">{node.expression}</span>;
    case "menu":
      return (
        <span className="text-ink2">
          {node.choices.length} choice{node.choices.length === 1 ? "" : "s"}
        </span>
      );
    case "if":
      return (
        <span className="text-ink2">
          {node.branches.length} branch{node.branches.length === 1 ? "" : "es"}
        </span>
      );
  }
}

// ---------- insert-event UI for the new tools -------------------------------

const INSERT_OPTIONS = [
  { id: "pause", label: "Pause / beat", icon: Timer },
  { id: "setvar", label: "Set variable", icon: Variable },
  { id: "show", label: "Show / move character", icon: Image },
  { id: "with", label: "With effect", icon: Wand2 },
  { id: "flash", label: "Color flash", icon: Zap },
] as const;

type InsertId = (typeof INSERT_OPTIONS)[number]["id"];

function InsertEvent({ labelName }: { labelName: string }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<InsertId | null>(null);
  const popupRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        setOpen(false);
        setActive(null);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  return (
    <div className="border-t border-line pt-3 mt-3 relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full inline-flex items-center justify-center gap-1 px-2 py-1.5 text-xs rounded border border-dashed border-line text-ink3 hover:text-ink hover:border-line"
      >
        <Plus className="w-3 h-3" />
        Insert event
      </button>
      {open && (
        <div
          ref={popupRef}
          className="absolute left-0 right-0 mt-1 bg-card border border-line rounded shadow-lg z-10 overflow-hidden"
        >
          {active === null ? (
            <ul className="py-1">
              {INSERT_OPTIONS.map((opt) => (
                <li key={opt.id}>
                  <button
                    onClick={() => setActive(opt.id)}
                    className="w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-cardAlt text-left text-ink2 hover:text-ink"
                  >
                    <opt.icon className="w-3.5 h-3.5" />
                    {opt.label}
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <InsertForm
              kind={active}
              labelName={labelName}
              onClose={() => {
                setOpen(false);
                setActive(null);
              }}
              onBack={() => setActive(null)}
            />
          )}
        </div>
      )}
    </div>
  );
}

function InsertForm({
  kind,
  labelName,
  onClose,
  onBack,
}: {
  kind: InsertId;
  labelName: string;
  onClose: () => void;
  onBack: () => void;
}) {
  const qc = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const submit = useMutation({
    mutationFn: async (body: Record<string, unknown>) =>
      api<{ summary?: string; error?: string }>(
        `/api/labels/${encodeURIComponent(labelName)}/events/${kind}`,
        { method: "POST", json: body },
      ),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error);
        return;
      }
      qc.invalidateQueries({ queryKey: ["label-tree", labelName] });
      qc.invalidateQueries({ queryKey: ["graph"] });
      qc.invalidateQueries({ queryKey: ["variables"] });
      onClose();
    },
    onError: (err) => setError(String(err)),
  });

  return (
    <div className="p-3 space-y-2 text-xs">
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="text-[10px] text-ink3 hover:text-ink uppercase tracking-wide font-mono"
        >
          ← back
        </button>
        <button
          onClick={onClose}
          className="text-[10px] text-ink3 hover:text-ink"
          aria-label="Close"
        >
          ✕
        </button>
      </div>
      {kind === "pause" && (
        <PauseForm onSubmit={(body) => submit.mutate(body)} pending={submit.isPending} />
      )}
      {kind === "setvar" && (
        <SetvarForm onSubmit={(body) => submit.mutate(body)} pending={submit.isPending} />
      )}
      {kind === "show" && (
        <ShowForm onSubmit={(body) => submit.mutate(body)} pending={submit.isPending} />
      )}
      {kind === "with" && (
        <WithForm onSubmit={(body) => submit.mutate(body)} pending={submit.isPending} />
      )}
      {kind === "flash" && (
        <FlashForm onSubmit={(body) => submit.mutate(body)} pending={submit.isPending} />
      )}
      {error && <div className="text-rose-600">{error}</div>}
    </div>
  );
}

function PauseForm({
  onSubmit,
  pending,
}: {
  onSubmit: (body: Record<string, unknown>) => void;
  pending: boolean;
}) {
  const [duration, setDuration] = useState("0.5");
  return (
    <div className="space-y-1.5">
      <label className="text-ink3">Duration (s)</label>
      <input
        type="number"
        step="0.05"
        min="0"
        value={duration}
        onChange={(e) => setDuration(e.target.value)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
      />
      <SubmitBtn
        pending={pending}
        onClick={() => onSubmit({ duration: parseFloat(duration) })}
      />
    </div>
  );
}

function SetvarForm({
  onSubmit,
  pending,
}: {
  onSubmit: (body: Record<string, unknown>) => void;
  pending: boolean;
}) {
  const [name, setName] = useState("");
  const [value, setValue] = useState("");
  const [type, setType] = useState<"string" | "number" | "bool" | "null">("number");
  return (
    <div className="space-y-1.5">
      <label className="text-ink3">Variable name</label>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
        placeholder="trust_mei"
      />
      <label className="text-ink3">Value type</label>
      <select
        value={type}
        onChange={(e) => setType(e.target.value as typeof type)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
      >
        <option value="number">number</option>
        <option value="string">string</option>
        <option value="bool">boolean</option>
        <option value="null">null</option>
      </select>
      {type !== "null" && (
        <input
          value={type === "bool" ? value : value}
          onChange={(e) => setValue(e.target.value)}
          className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
          placeholder={type === "string" ? "hello" : type === "bool" ? "true / false" : "1"}
        />
      )}
      <SubmitBtn
        pending={pending}
        onClick={() => {
          let coerced: unknown = null;
          if (type === "string") coerced = value;
          else if (type === "number") coerced = parseFloat(value);
          else if (type === "bool") coerced = value.trim().toLowerCase() === "true";
          onSubmit({ name, value: coerced });
        }}
      />
    </div>
  );
}

function ShowForm({
  onSubmit,
  pending,
}: {
  onSubmit: (body: Record<string, unknown>) => void;
  pending: boolean;
}) {
  const [tag, setTag] = useState("");
  const [expression, setExpression] = useState("");
  const [position, setPosition] = useState("");
  const [transition, setTransition] = useState("");
  return (
    <div className="space-y-1.5">
      <label className="text-ink3">Image tag</label>
      <input
        value={tag}
        onChange={(e) => setTag(e.target.value)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
        placeholder="eileen"
      />
      <label className="text-ink3">Expression</label>
      <input
        value={expression}
        onChange={(e) => setExpression(e.target.value)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
        placeholder="happy"
      />
      <label className="text-ink3">Position</label>
      <input
        value={position}
        onChange={(e) => setPosition(e.target.value)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
        placeholder="left"
      />
      <label className="text-ink3">Transition</label>
      <input
        value={transition}
        onChange={(e) => setTransition(e.target.value)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
        placeholder="dissolve"
      />
      <SubmitBtn
        pending={pending}
        onClick={() => {
          const body: Record<string, unknown> = { tag };
          if (expression.trim()) body.expression = expression.trim();
          if (position.trim()) body.position = position.trim();
          if (transition.trim()) body.transition = transition.trim();
          onSubmit(body);
        }}
      />
    </div>
  );
}

function WithForm({
  onSubmit,
  pending,
}: {
  onSubmit: (body: Record<string, unknown>) => void;
  pending: boolean;
}) {
  const [expression, setExpression] = useState("hpunch");
  return (
    <div className="space-y-1.5">
      <label className="text-ink3">Transition expression</label>
      <input
        value={expression}
        onChange={(e) => setExpression(e.target.value)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
        placeholder="hpunch / Dissolve(0.5)"
      />
      <SubmitBtn
        pending={pending}
        onClick={() => onSubmit({ expression })}
      />
    </div>
  );
}

function FlashForm({
  onSubmit,
  pending,
}: {
  onSubmit: (body: Record<string, unknown>) => void;
  pending: boolean;
}) {
  const [color, setColor] = useState("#ffffff");
  const [duration, setDuration] = useState("0.25");
  return (
    <div className="space-y-1.5">
      <label className="text-ink3">Color</label>
      <div className="flex gap-1.5 items-center">
        <input
          type="color"
          value={color}
          onChange={(e) => setColor(e.target.value)}
          className="w-8 h-7 border border-line rounded cursor-pointer"
        />
        <input
          value={color}
          onChange={(e) => setColor(e.target.value)}
          className="flex-1 px-2 py-1 border border-line rounded font-mono bg-card text-ink"
        />
      </div>
      <label className="text-ink3">Duration (s)</label>
      <input
        type="number"
        step="0.05"
        min="0"
        value={duration}
        onChange={(e) => setDuration(e.target.value)}
        className="w-full px-2 py-1 border border-line rounded font-mono bg-card text-ink"
      />
      <SubmitBtn
        pending={pending}
        onClick={() => onSubmit({ color, duration: parseFloat(duration) })}
      />
    </div>
  );
}

function SubmitBtn({ pending, onClick }: { pending: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      disabled={pending}
      className="w-full px-2 py-1 text-xs rounded text-white disabled:opacity-50 mt-1"
      style={{ background: "var(--rp-accent)" }}
    >
      {pending ? "Inserting…" : "Insert"}
    </button>
  );
}
