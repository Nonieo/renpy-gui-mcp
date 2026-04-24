import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Info, Music as MusicIcon, Pencil, Sliders, X } from "lucide-react";
import { api } from "@/api/client";
import type { AudioListing, LabelInfo } from "@/api/types";

// Cross-scene view: every label with its current music play pulled from the
// audio-listing's `plays` array, joined by file + line range against the
// label index. Per-scene edits round-trip through /api/labels/{name}/music,
// the same endpoint the Scene Inspector already uses.

interface MusicPlay {
  channel: string;
  asset: string;
  file: string;
  line: number;
}

interface SceneMusicRow {
  label: LabelInfo;
  play: MusicPlay | null;
}

// Matches the Assets panel's "this looks like music" heuristic so the two
// views agree on what counts as music (vs SFX).
const MUSIC_NAME_RE = /theme|bgm|music/i;
function isMusicAsset(path: string): boolean {
  return MUSIC_NAME_RE.test(path) || path.endsWith(".ogg");
}

export function Music() {
  const labels = useQuery({
    queryKey: ["labels"],
    queryFn: () => api<{ labels: LabelInfo[]; count: number }>("/api/labels"),
  });
  const audio = useQuery({
    queryKey: ["audio"],
    queryFn: () => api<AudioListing>("/api/audio"),
  });
  const [editing, setEditing] = useState<SceneMusicRow | null>(null);

  const rows = useMemo<SceneMusicRow[]>(() => {
    if (!labels.data || !audio.data) return [];
    // A label's music is the last music-channel play that falls inside the
    // label's source range. "Last wins" matches Ren'Py's runtime: later
    // `play music` calls override earlier ones within the same scene.
    const musicPlays = audio.data.plays.filter((p) => p.channel === "music");
    return labels.data.labels.map((label) => {
      const inside = musicPlays.filter(
        (p) =>
          p.file === label.file &&
          p.line >= label.start_line &&
          p.line <= label.end_line,
      );
      const play = inside.length > 0 ? inside[inside.length - 1] : null;
      return { label, play };
    });
  }, [labels.data, audio.data]);

  const musicLibrary = useMemo(() => {
    if (!audio.data) return [];
    return audio.data.files
      .filter((f) => isMusicAsset(f.asset_path))
      .sort((a, b) => a.asset_path.localeCompare(b.asset_path));
  }, [audio.data]);

  return (
    <div className="p-8 h-full overflow-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-zinc-800">Music</h1>
      </div>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-zinc-600 uppercase tracking-wide mb-3">
          Per-scene music
        </h2>

        {(labels.isLoading || audio.isLoading) && (
          <p className="text-sm text-zinc-500">Loading…</p>
        )}
        {(labels.error || audio.error) && (
          <p className="text-sm text-red-600">
            Error: {String(labels.error ?? audio.error)}
          </p>
        )}

        {labels.data && audio.data && (
          <div className="bg-card border border-zinc-200 rounded-md overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-zinc-50 text-zinc-500 text-xs uppercase tracking-wide">
                  <th className="text-left px-4 py-2 font-medium">Scene</th>
                  <th className="text-left px-4 py-2 font-medium">Music</th>
                  <th className="text-left px-4 py-2 font-medium w-48">Location</th>
                  <th className="px-4 py-2 w-12"></th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-4 py-6 text-center text-zinc-500 text-sm">
                      No labels in this project yet.
                    </td>
                  </tr>
                )}
                {rows.map((row) => (
                  <SceneRow
                    key={row.label.name}
                    row={row}
                    onEdit={() => setEditing(row)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="mb-8">
        <h2 className="text-sm font-semibold text-zinc-600 uppercase tracking-wide mb-3">
          Music library
        </h2>

        {audio.data && musicLibrary.length === 0 && (
          <div className="bg-card border border-dashed border-zinc-300 rounded-lg p-10 text-center">
            <MusicIcon className="w-8 h-8 mx-auto text-zinc-400 mb-3" />
            <p className="text-sm text-zinc-600">
              No music files found under <code className="font-mono">game/audio/</code>.
            </p>
            <p className="text-xs text-zinc-500 mt-1">
              Drop tracks into the project's audio folder (or upload via the Assets panel)
              and they'll appear here.
            </p>
          </div>
        )}

        {musicLibrary.length > 0 && (
          <div className="space-y-2">
            {musicLibrary.map((f) => {
              const usedBy =
                audio.data?.plays.filter(
                  (p) => p.channel === "music" && f.asset_path.endsWith(p.asset),
                ).length ?? 0;
              return (
                <div
                  key={f.asset_path}
                  className="bg-card border border-zinc-200 rounded-md p-3 flex items-center justify-between"
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate font-mono">{f.asset_path}</div>
                    <div className="text-xs text-zinc-500">
                      {(f.size_bytes / 1024).toFixed(1)} KB
                      {usedBy > 0 && ` · played in ${usedBy} scene${usedBy === 1 ? "" : "s"}`}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <section className="mb-4">
        <h2 className="text-sm font-semibold text-zinc-600 uppercase tracking-wide mb-3">
          Mixer
        </h2>
        <div className="bg-card border border-dashed border-zinc-300 rounded-lg p-6 flex items-start gap-3">
          <Sliders className="w-5 h-5 text-zinc-400 mt-0.5 shrink-0" />
          <div className="text-sm text-zinc-600">
            <p className="font-medium text-zinc-700">Global volume & channel mixing — coming soon</p>
            <p className="text-xs text-zinc-500 mt-1">
              Ren'Py channels (<code className="font-mono">music</code>,{" "}
              <code className="font-mono">sound</code>,{" "}
              <code className="font-mono">voice</code>, ambient) and their default
              volumes live in <code className="font-mono">options.rpy</code>; per-channel
              fades are wired through <code className="font-mono">renpy.music.set_volume()</code>.
              Both need new MCP tools before this card becomes interactive.
            </p>
          </div>
        </div>
      </section>

      <p className="mt-4 text-xs text-zinc-500 flex items-start gap-1.5">
        <Info className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          Per-scene edits go through <code className="font-mono">set_scene_music</code>,
          the same MCP tool the Scene Inspector uses. Clearing a track emits
          <code className="font-mono"> stop music</code>; multiple{" "}
          <code className="font-mono">play music</code> calls within one label show the
          last one here.
        </span>
      </p>

      {editing && (
        <SceneMusicModal
          row={editing}
          library={musicLibrary.map((f) => f.asset_path)}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function SceneRow({ row, onEdit }: { row: SceneMusicRow; onEdit: () => void }) {
  const { label, play } = row;
  return (
    <tr className="border-t border-zinc-100">
      <td className="px-4 py-2 font-mono text-zinc-800">{label.name}</td>
      <td className="px-4 py-2">
        {play ? (
          <span className="font-mono text-xs text-zinc-700" title={play.asset}>
            {play.asset}
          </span>
        ) : (
          <span className="text-xs text-zinc-400 italic">—</span>
        )}
      </td>
      <td className="px-4 py-2 text-xs text-zinc-500 font-mono">
        {play ? `${play.file}:${play.line}` : `${label.file}:${label.start_line}`}
      </td>
      <td className="px-4 py-2 text-right">
        <button
          onClick={onEdit}
          className="p-1 text-zinc-400 hover:text-zinc-700"
          title="Edit music"
        >
          <Pencil className="w-4 h-4" />
        </button>
      </td>
    </tr>
  );
}

function SceneMusicModal({
  row,
  library,
  onClose,
}: {
  row: SceneMusicRow;
  library: string[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [asset, setAsset] = useState(row.play?.asset ?? "");
  const [loop, setLoop] = useState(false);
  const [fadein, setFadein] = useState("");
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        asset: asset.trim(),
        loop,
        validate_asset: asset.trim().length > 0,
      };
      const fadeinNum = fadein.trim() === "" ? null : Number(fadein);
      if (fadeinNum !== null && !Number.isNaN(fadeinNum)) {
        payload.fadein = fadeinNum;
      }
      return api<{ summary?: string; error?: string }>(
        `/api/labels/${encodeURIComponent(row.label.name)}/music`,
        { method: "POST", json: payload },
      );
    },
    onSuccess: (data) => {
      if (data.error) {
        setError(data.error);
        return;
      }
      qc.invalidateQueries({ queryKey: ["labels"] });
      qc.invalidateQueries({ queryKey: ["audio"] });
      qc.invalidateQueries({ queryKey: ["label", row.label.name] });
      onClose();
    },
    onError: (err) => setError(String(err)),
  });

  const isStop = asset.trim() === "";

  return (
    <div className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-50">
      <div className="bg-card w-full sm:max-w-md rounded-t-lg sm:rounded-lg shadow-lg">
        <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-200">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wide text-zinc-400">Scene music</div>
            <h2 className="font-semibold truncate">{row.label.name}</h2>
          </div>
          <button onClick={onClose} className="p-1 text-zinc-400 hover:text-zinc-700">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <label className="block text-sm">
            <span className="block text-xs font-medium text-zinc-500 mb-1">Asset path</span>
            <input
              list="music-library-options"
              type="text"
              value={asset}
              autoFocus
              onChange={(e) => {
                setAsset(e.target.value);
                setError(null);
              }}
              placeholder="audio/spring_theme.ogg"
              className="w-full px-3 py-1.5 border border-zinc-200 rounded-md text-sm font-mono"
            />
            <datalist id="music-library-options">
              {library.map((path) => (
                <option key={path} value={path} />
              ))}
            </datalist>
            <span className="block mt-1 text-[10px] text-zinc-500">
              Leave blank to emit <code className="font-mono">stop music</code>.
            </span>
          </label>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={loop}
              onChange={(e) => setLoop(e.target.checked)}
              disabled={isStop}
              className="h-4 w-4"
            />
            <span className={isStop ? "text-zinc-400" : "text-zinc-700"}>Loop</span>
          </label>

          <label className="block text-sm">
            <span className="block text-xs font-medium text-zinc-500 mb-1">
              Fade-in (seconds, optional)
            </span>
            <input
              type="number"
              min="0"
              step="0.1"
              value={fadein}
              onChange={(e) => setFadein(e.target.value)}
              disabled={isStop}
              placeholder="0.5"
              className="w-full px-3 py-1.5 border border-zinc-200 rounded-md text-sm font-mono disabled:bg-zinc-50 disabled:text-zinc-400"
            />
          </label>

          {error && <div className="text-xs text-red-600">{error}</div>}
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-zinc-200 bg-zinc-50">
          <button
            onClick={onClose}
            className="px-3 py-1.5 text-sm rounded-md border border-zinc-200 hover:bg-white"
          >
            Cancel
          </button>
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="px-3 py-1.5 text-sm rounded-md bg-accent text-white hover:bg-indigo-600 disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : isStop ? "Stop music" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
