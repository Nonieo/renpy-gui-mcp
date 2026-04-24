/**
 * Parse a label's source into a structured view used by the Scene Inspector.
 *
 * This is intentionally tolerant: anything we don't recognize (menu blocks,
 * if-branches, python lines, transforms) is dropped from the structured
 * fields and surfaced as `unparsed` so the inspector can warn the user
 * before they overwrite something they didn't see.
 */

export interface ParsedDialogue {
  character: string | null;
  text: string;
  line: number; // 1-based, relative to the file (not the label)
  raw: string;
}

export interface ParsedShow {
  expression: string; // everything after `show ` (e.g. "eileen happy at left")
  line: number;
}

export interface ParsedJump {
  kind: "jump" | "call";
  target: string;
  line: number;
}

export interface ParsedScene {
  background: string | null; // e.g. "bg park"
  music: string | null; // asset path (e.g. "audio/spring_theme.ogg")
  shows: ParsedShow[];
  dialogue: ParsedDialogue[];
  jumps: ParsedJump[];
  unparsed: { line: number; raw: string }[];
  endsWithReturn: boolean;
}

const SCENE_RE = /^\s+scene\s+(.+?)\s*$/;
const PLAY_MUSIC_RE = /^\s+play\s+music\s+"([^"]+)"/;
const SHOW_RE = /^\s+show\s+(.+?)\s*$/;
const JUMP_RE = /^\s+jump\s+(\w+)\s*$/;
const CALL_RE = /^\s+call\s+(\w+)\b/;
const RETURN_RE = /^\s+return\s*$/;
// say-statements: optional character var, then a quoted string. Allow escaped quotes.
const SAY_NAMED_RE = /^\s+([A-Za-z_]\w*)\s+"((?:\\.|[^"\\])*)"\s*$/;
const SAY_NARR_RE = /^\s+"((?:\\.|[^"\\])*)"\s*$/;

export function parseLabelSource(source: string, headerLine: number): ParsedScene {
  const lines = source.split("\n");
  const result: ParsedScene = {
    background: null,
    music: null,
    shows: [],
    dialogue: [],
    jumps: [],
    unparsed: [],
    endsWithReturn: false,
  };

  // Skip the `label X:` header (index 0).
  for (let i = 1; i < lines.length; i++) {
    const raw = lines[i];
    const stripped = raw.trim();
    const fileLine = headerLine + i; // headerLine is 1-based; lines[0] is the header

    if (stripped === "" || stripped.startsWith("#")) continue;

    let m: RegExpMatchArray | null;
    if ((m = raw.match(SCENE_RE))) {
      // The first scene we find is the canonical background; later `scene`
      // calls (rare but legal) get bumped to `unparsed` so the inspector
      // doesn't silently overwrite them.
      if (result.background === null) result.background = m[1];
      else result.unparsed.push({ line: fileLine, raw: stripped });
      continue;
    }
    if ((m = raw.match(PLAY_MUSIC_RE))) {
      if (result.music === null) result.music = m[1];
      else result.unparsed.push({ line: fileLine, raw: stripped });
      continue;
    }
    if ((m = raw.match(SHOW_RE))) {
      result.shows.push({ expression: m[1], line: fileLine });
      continue;
    }
    if ((m = raw.match(JUMP_RE))) {
      result.jumps.push({ kind: "jump", target: m[1], line: fileLine });
      continue;
    }
    if ((m = raw.match(CALL_RE))) {
      result.jumps.push({ kind: "call", target: m[1], line: fileLine });
      continue;
    }
    if (RETURN_RE.test(raw)) {
      result.endsWithReturn = true;
      continue;
    }
    if ((m = raw.match(SAY_NAMED_RE))) {
      result.dialogue.push({ character: m[1], text: m[2], line: fileLine, raw: stripped });
      continue;
    }
    if ((m = raw.match(SAY_NARR_RE))) {
      result.dialogue.push({ character: null, text: m[1], line: fileLine, raw: stripped });
      continue;
    }
    result.unparsed.push({ line: fileLine, raw: stripped });
  }

  return result;
}
