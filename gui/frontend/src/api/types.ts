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

export interface BranchGraph {
  nodes: { id: string; file: string; start_line: number; end_line: number; say_count: number }[];
  edges: { from: string; to: string; kind: string }[];
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
