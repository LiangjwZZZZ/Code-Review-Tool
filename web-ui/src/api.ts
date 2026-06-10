import type { Report } from './types';

const API_BASE = '/api';

export interface ReportSummary {
  commit: string;
  commit_message: string;
  commit_body: string;
  author: string;
  commit_time: string;
  repo_name: string;
  risk_level: string;
  changes_count: number;
  created_at: string;
}

export interface CommitNode {
  hash: string;
  parents: string[];
  message: string;
  author: string;
  time: string;
  analyzed: boolean;
}

export interface BranchInfo {
  name: string;
  hash: string;
}

export interface CommitData {
  commits: CommitNode[];
  branches: BranchInfo[];
  repo_name: string;
}

export async function fetchReportsList(): Promise<ReportSummary[]> {
  const res = await fetch(`${API_BASE}/reports`);
  if (!res.ok) throw new Error('Failed to fetch reports');
  return res.json();
}

export async function fetchReport(commitHash: string): Promise<Report> {
  const res = await fetch(`${API_BASE}/reports/${commitHash}`);
  if (!res.ok) throw new Error('Report not found');
  return res.json();
}

export async function fetchCommits(repo: string = '.', branch: string = ''): Promise<CommitData> {
  let url = `${API_BASE}/commits?repo=${encodeURIComponent(repo)}`;
  if (branch) url += `&branch=${encodeURIComponent(branch)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch commits');
  return res.json();
}

export async function triggerAnalysis(commitHash: string, repo: string = '.', quick: boolean = false): Promise<{ status: string; risk_level: string; commit_hash: string }> {
  const res = await fetch(`${API_BASE}/analyze/${commitHash}?repo=${encodeURIComponent(repo)}&quick=${quick}`, { method: 'POST' });
  if (!res.ok) {
    const body = await res.json();
    throw new Error(body.error || 'Analysis failed');
  }
  return res.json();
}

// ── Launcher API ─────────────────────────────────────────────────────────────

export interface LauncherConfigData {
  api_key: string;
  model: string;
  host: string;
  port: number;
  repo_path: string;
  commit_hash: string;
  api_type: string;
  log_dir: string;
  repos?: string[];
  current_repo?: string;
  global_branch?: string;
  per_repo_branches?: Record<string, string>;
  gerrit_username?: string;
  gerrit_password?: string;
  git_path?: string;
}

export async function fetchLauncherConfig(): Promise<LauncherConfigData> {
  const res = await fetch(`${API_BASE}/launcher/config`);
  return res.json();
}

export async function saveLauncherConfig(config: LauncherConfigData): Promise<LauncherConfigData> {
  const res = await fetch(`${API_BASE}/launcher/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  return res.json();
}

export async function shutdownServer(): Promise<void> {
  await fetch(`${API_BASE}/shutdown`, { method: 'POST' });
}

export interface CommitPreview {
  hash: string;
  message: string;
  body: string;
  author: string;
  time: string;
  changes: { file: string; added: number; removed: number; hunks: string[] }[];
}

export async function fetchCommitPreview(commitHash: string, repo: string = '.'): Promise<CommitPreview> {
  const res = await fetch(`${API_BASE}/commits/${commitHash}/preview?repo=${encodeURIComponent(repo)}`);
  if (!res.ok) throw new Error('Failed to fetch commit preview');
  return res.json();
}

export async function fetchDiff(commitHash: string, repo: string, file?: string): Promise<{ diff: string }> {
  let url = `${API_BASE}/diff/${commitHash}?repo=${encodeURIComponent(repo)}`;
  if (file) url += `&file=${encodeURIComponent(file)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch diff');
  return res.json();
}

export async function triggerFileAnalysis(commitHash: string, file: string, repo: string = '.'): Promise<{ findings: any[]; analysis_status: string }> {
  const res = await fetch(`${API_BASE}/reports/${commitHash}/analyze-file?file=${encodeURIComponent(file)}&repo=${encodeURIComponent(repo)}`, { method: 'POST' });
  if (!res.ok) {
    const body = await res.json();
    throw new Error(body.error || 'Analysis failed');
  }
  return res.json();
}

export async function fetchModules(commitHash: string): Promise<{ modules: any[]; cross_module_impacts: any[]; file_modules: Record<string, string> }> {
  const res = await fetch(`${API_BASE}/reports/${commitHash}/modules`);
  if (!res.ok) throw new Error('Failed to fetch modules');
  return res.json();
}

export async function triggerGerritAnalysis(gerritUrl: string, repo?: string): Promise<{ status: string; commit_hash: string; risk_level: string; report_url: string }> {
  let url = `${API_BASE}/gerrit/analyze?gerrit_url=${encodeURIComponent(gerritUrl)}`;
  if (repo) url += `&repo=${encodeURIComponent(repo)}`;
  const res = await fetch(url, { method: 'POST' });
  if (!res.ok) {
    const body = await res.json();
    throw new Error(body.error || 'Gerrit analysis failed');
  }
  return res.json();
}

export function startLaunchStream(config: LauncherConfigData, onMessage: (data: any) => void, onError: (err: string) => void): AbortController {
  const controller = new AbortController();
  fetch(`${API_BASE}/launcher/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
    signal: controller.signal,
  }).then(async (res) => {
    const reader = res.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          onMessage(JSON.parse(line));
        } catch { /* skip partial */ }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') onError(err.message);
  });
  return controller;
}
