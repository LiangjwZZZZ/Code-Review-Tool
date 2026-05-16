export interface DiffChange {
  file: string;
  added: number;
  removed: number;
  hunks: string[];
}

export interface ImpactItem {
  symbol: string;
  symbol_kind: string;
  file: string;
  risk: string;
  direction: string;
  affected_symbols: string[];
  affected_processes: string[];
  summary: string;
}

export interface ReviewFinding {
  category: string;
  severity: string;
  message: string;
  suggestion: string;
}

export interface Report {
  commit_hash: string;
  commit_message: string;
  author: string;
  risk_level: string;
  changes: DiffChange[];
  impacts: ImpactItem[];
  findings: ReviewFinding[];
  summary: string;
  created_at: string;
}
