export interface Overview {
  project_root: string;
  files: string[];
  counts: Record<string, number>;
  labels: string[];
  characters: { var: string; display_name: string | null }[];
  warnings: string[];
}

export interface LabelInfo {
  name: string;
  file: string;
  start_line: number;
  end_line: number;
  say_count: number;
}

export interface CharacterInfo {
  var: string;
  display_name: string | null;
  raw_args: string;
  file: string;
  line: number;
}

export type LabelKind = "start" | "scene" | "choice" | "ending";

export interface BranchGraphNode {
  id: string;
  file: string;
  start_line: number;
  end_line: number;
  say_count: number;
  /** Inferred from the parsed label tree; missing on legacy responses. */
  kind?: LabelKind;
}

export interface BranchGraphEdge {
  from: string;
  to: string;
  /** "jump" or "call" — used by the Story Map to render call edges differently. */
  kind: string;
  /** POSIX path to the file that contains the jump statement. */
  from_file: string;
  /** 1-based source line of the jump/call statement. */
  from_line: number;
}

export interface BranchGraph {
  nodes: BranchGraphNode[];
  edges: BranchGraphEdge[];
}

export interface CanvasPosition {
  x: number;
  y: number;
}

export interface CanvasPositions {
  version: number;
  labels: Record<string, CanvasPosition>;
  count: number;
}

// ---------- read_label_tree response shape (Phase 4 Inspector) ---------------

export type LabelTreeNode =
  | { kind: "say"; line: number; character: string | null; text: string }
  | { kind: "scene"; line: number; expression: string }
  | { kind: "show"; line: number; expression: string }
  | { kind: "hide"; line: number; expression: string }
  | {
      kind: "play";
      line: number;
      channel: string;
      asset: string;
      options: string | null;
    }
  | { kind: "stop"; line: number; channel: string; options: string | null }
  | { kind: "pause"; line: number; duration: string | null }
  | { kind: "jump"; line: number; target: string }
  | { kind: "call"; line: number; target: string; rest: string | null }
  | { kind: "return"; line: number }
  | { kind: "with"; line: number; expression: string }
  | { kind: "set"; line: number; expression: string }
  | {
      kind: "menu";
      line: number;
      menu_label: string | null;
      choices: {
        text: string;
        condition: string | null;
        line: number;
        body: LabelTreeNode[];
      }[];
    }
  | {
      kind: "if";
      line: number;
      branches: {
        kind: "if" | "elif" | "else";
        condition: string | null;
        line: number;
        body: LabelTreeNode[];
      }[];
    };

export interface LabelTreeShorthand {
  background: string | null;
  music: string | null;
  outgoing_targets: string[];
  ends_with_return: boolean;
}

export interface LabelTree {
  label: {
    name: string;
    file: string;
    start_line: number;
    end_line: number;
    say_count: number;
  };
  kind: LabelKind;
  body: LabelTreeNode[];
  shorthand: LabelTreeShorthand;
  unparsed: { line: number; raw: string }[];
}

// ---------- get_choice_graph response shape (Phase 6 Choice View) ------------

export interface ChoiceBranch {
  text: string;
  condition: string | null;
  line: number;
  /** First top-level jump/call target in the branch's body, if any. */
  target: string | null;
  target_kind: "jump" | "call" | null;
  target_line: number | null;
}

export interface ChoiceRecord {
  label: string;
  file: string;
  /** Source line of the `menu:` keyword. */
  line: number;
  menu_label: string | null;
  branches: ChoiceBranch[];
}

export interface ChoiceGraph {
  choices: ChoiceRecord[];
  count: number;
}

// ---------- translation surface (Phase 8) ------------------------------------

export interface TranslationCoverageRow {
  language: string;
  total: number;
  translated: number;
  stale: number;
  percent: number;
}

export interface TranslationCoverage {
  languages: TranslationCoverageRow[];
  count: number;
}

export interface StaleTranslationEntry {
  language: string;
  kind: "say" | "string";
  block_id: string;
  source: string | null;
  target: string;
  file: string;
  line: number;
}

export interface StaleTranslations {
  stale: StaleTranslationEntry[];
  count: number;
}

export interface ImageInfo {
  name: string;
  kind: "alias" | "auto" | "layered";
  value?: string;
  asset_path?: string;
  file?: string;
  line?: number;
}

export interface AudioListing {
  files: { asset_path: string; size_bytes: number }[];
  plays: { channel: string; asset: string; file: string; line: number }[];
}

export interface VariableInfo {
  name: string;
  kind: "default" | "define";
  value: string;
  file: string;
  line: number;
}

export interface ScreenInfo {
  name: string;
  file: string;
  start_line: number;
  end_line: number;
}
