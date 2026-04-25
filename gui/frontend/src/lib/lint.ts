export type Severity = "error" | "warning" | "notice";

export interface ParsedFinding {
  severity: Severity;
  file: string | null;
  line: number | null;
  message: string;
}

export interface LintReport {
  returncode: number;
  summary: string | null;
  stdout: string;
  stderr: string;
  error?: string;
}

const FINDING_RE = /^File "([^"]+)", line (\d+): (?:(error|warning): )?(.+)$/;

function classify(rest: string, prefix: string | undefined): Severity {
  if (prefix === "error") return "error";
  if (prefix === "warning") return "warning";
  if (/never used|cannot find|missing/i.test(rest)) return "warning";
  return "notice";
}

export function parseFindings(stdout: string): ParsedFinding[] {
  const out: ParsedFinding[] = [];
  for (const line of stdout.split("\n")) {
    const m = line.match(FINDING_RE);
    if (!m) continue;
    out.push({
      severity: classify(m[3], m[2]),
      file: m[1],
      line: Number.parseInt(m[2], 10),
      message: m[3],
    });
  }
  return out;
}
