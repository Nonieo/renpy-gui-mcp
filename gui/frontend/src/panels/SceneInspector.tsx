import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Image, Music, MessageSquare, GitBranch, AlertTriangle, X } from "lucide-react";
import { api } from "@/api/client";
import type { CharacterInfo } from "@/api/types";
import { parseLabelSource, type ParsedScene } from "@/lib/parseLabel";

interface LabelRead {
  label: { name: string; file: string; start_line: number; end_line: number; say_count: number };
  source: string;
}

export function SceneInspector({ name, onClose }: { name: string; onClose: () => void }) {
  const detail = useQuery({
    queryKey: ["label", name],
    queryFn: () => api<LabelRead>(`/api/labels/${encodeURIComponent(name)}`),
  });
  const characters = useQuery({
    queryKey: ["characters"],
    queryFn: () => api<{ characters: CharacterInfo[] }>("/api/characters"),
  });

  const parsed = useMemo<ParsedScene | null>(() => {
    if (!detail.data) return null;
    return parseLabelSource(detail.data.source, detail.data.label.start_line);
  }, [detail.data]);

  return (
    <aside className="w-96 shrink-0 border-l border-zinc-200 bg-card flex flex-col">
      <header className="px-5 py-3 border-b border-zinc-200 flex items-center justify-between">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wide text-zinc-400">Scene</div>
          <h2 className="font-semibold truncate">{name}</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-zinc-400 hover:text-zinc-700"
          title="Close inspector"
        >
          <X className="w-4 h-4" />
        </button>
      </header>

      <div className="flex-1 overflow-auto px-5 py-4 space-y-5 text-sm">
        {detail.isLoading && <p className="text-zinc-500">Loading scene…</p>}
        {detail.error && (
          <p className="text-red-600">Error: {String(detail.error)}</p>
        )}

        {parsed && detail.data && (
          <>
            <Section icon={<Image className="w-4 h-4" />} title="Background">
              <BackgroundField labelName={name} current={parsed.background} />
            </Section>

            <Section icon={<Music className="w-4 h-4" />} title="Music">
              <MusicField labelName={name} current={parsed.music} />
            </Section>

            <Section icon={<ChevronRight className="w-4 h-4" />} title={`Characters on screen (${parsed.shows.length})`}>
              {parsed.shows.length === 0 ? (
                <p className="text-zinc-500 text-xs">No `show` statements in this label.</p>
              ) : (
                <ul className="space-y-1">
                  {parsed.shows.map((s) => (
                    <li key={s.line} className="font-mono text-xs text-zinc-700">
                      {s.expression}
                    </li>
                  ))}
                </ul>
              )}
            </Section>

            <Section icon={<MessageSquare className="w-4 h-4" />} title={`Dialogue (${parsed.dialogue.length})`}>
              <DialogueList parsed={parsed} />
              <AddDialogueForm labelName={name} characters={characters.data?.characters ?? []} />
            </Section>

            <Section icon={<GitBranch className="w-4 h-4" />} title={`Outgoing (${parsed.jumps.length})`}>
              {parsed.jumps.length === 0 ? (
                <p className="text-zinc-500 text-xs">
                  {parsed.endsWithReturn ? "Ends with `return`." : "No outgoing jumps."}
                </p>
              ) : (
                <ul className="space-y-1">
                  {parsed.jumps.map((j) => (
                    <li key={j.line} className="text-xs">
                      <span className="font-mono text-zinc-500">{j.kind}</span>{" "}
                      <span className="font-mono font-medium">{j.target}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Section>

            {parsed.unparsed.length > 0 && (
              <Section
                icon={<AlertTriangle className="w-4 h-4 text-amber-500" />}
                title={`Unparsed (${parsed.unparsed.length})`}
              >
                <p className="text-xs text-zinc-500 mb-2">
                  These lines weren't recognized by the inspector. Edit them with
                  the renpy-mcp tools or a text editor — the GUI will not
                  modify them.
                </p>
                <ul className="space-y-1 font-mono text-[11px] text-zinc-600">
                  {parsed.unparsed.map((u) => (
                    <li key={u.line}>
                      <span className="text-zinc-400">{u.line}:</span> {u.raw}
                    </li>
                  ))}
                </ul>
              </Section>
            )}

            <div className="text-[10px] text-zinc-400 font-mono pt-2 border-t border-zinc-100">
              {detail.data.label.file}:{detail.data.label.start_line}–
              {detail.data.label.end_line}
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
      <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-500 mb-2">
        {icon}
        {title}
      </h3>
      <div className="pl-1">{children}</div>
    </section>
  );
}

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
          // Empty string tells the backend to emit `stop music`. Otherwise we
          // send the asset path; backend defaults validate_asset=true so the
          // user gets a clear error when the file is missing.
          json: { asset: draft.trim(), loop, validate_asset: draft.trim() !== "" },
        },
      ),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error);
        return;
      }
      qc.invalidateQueries({ queryKey: ["label", labelName] });
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
        className="w-full px-2 py-1.5 border border-zinc-200 rounded text-xs font-mono"
      />
      <label className="flex items-center gap-1.5 text-xs text-zinc-600">
        <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} />
        loop
      </label>
      {error && <div className="text-xs text-red-600">{error}</div>}
      {dirty && (
        <button
          onClick={() => setMusic.mutate()}
          disabled={setMusic.isPending}
          className="px-2 py-1 text-xs rounded bg-accent text-white hover:bg-indigo-600 disabled:opacity-50"
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
      qc.invalidateQueries({ queryKey: ["label", labelName] });
      qc.invalidateQueries({ queryKey: ["graph"] });
    },
    onError: (err) => setError(String(err)),
  });

  if (current === null && !dirty) {
    return (
      <p className="text-xs text-zinc-500">
        No `scene` line — this label doesn't set a background. Use the renpy-mcp
        tools to add one for now.
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
        className="w-full px-2 py-1.5 border border-zinc-200 rounded text-xs font-mono"
      />
      {error && <div className="text-xs text-red-600">{error}</div>}
      {dirty && (
        <button
          onClick={() => swap.mutate()}
          disabled={swap.isPending}
          className="px-2 py-1 text-xs rounded bg-accent text-white hover:bg-indigo-600 disabled:opacity-50"
        >
          {swap.isPending ? "Saving…" : "Swap background"}
        </button>
      )}
    </div>
  );
}

function DialogueList({ parsed }: { parsed: ParsedScene }) {
  if (parsed.dialogue.length === 0) {
    return <p className="text-xs text-zinc-500">No dialogue yet.</p>;
  }
  return (
    <ul className="space-y-1.5 mb-3">
      {parsed.dialogue.map((d) => (
        <li key={d.line} className="text-xs leading-relaxed">
          {d.character ? (
            <span className="font-mono font-semibold text-zinc-800">{d.character}</span>
          ) : (
            <span className="font-mono text-zinc-400 italic">narration</span>
          )}{" "}
          <span className="text-zinc-700">"{d.text}"</span>
        </li>
      ))}
    </ul>
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
        {
          method: "POST",
          json: { character: character || null, text },
        },
      ),
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error);
        return;
      }
      setText("");
      qc.invalidateQueries({ queryKey: ["label", labelName] });
      qc.invalidateQueries({ queryKey: ["graph"] });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (err) => setError(String(err)),
  });

  return (
    <div className="space-y-1.5 border-t border-zinc-100 pt-3">
      <div className="flex gap-1.5">
        <select
          value={character}
          onChange={(e) => setCharacter(e.target.value)}
          className="px-2 py-1.5 border border-zinc-200 rounded text-xs font-mono w-24"
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
          placeholder="Add a line…"
          className="flex-1 px-2 py-1.5 border border-zinc-200 rounded text-xs"
          onKeyDown={(e) => {
            if (e.key === "Enter" && text.trim() && !append.isPending) append.mutate();
          }}
        />
      </div>
      {error && <div className="text-xs text-red-600">{error}</div>}
      <button
        onClick={() => append.mutate()}
        disabled={!text.trim() || append.isPending}
        className="px-2 py-1 text-xs rounded bg-zinc-800 text-white hover:bg-zinc-900 disabled:opacity-40"
      >
        {append.isPending ? "Adding…" : "Add line"}
      </button>
    </div>
  );
}
