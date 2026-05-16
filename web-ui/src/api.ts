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

export async function fetchDiff(commitHash: string, repo: string, file?: string): Promise<{ diff: string }> {
  let url = `${API_BASE}/diff/${commitHash}?repo=${encodeURIComponent(repo)}`;
  if (file) url += `&file=${encodeURIComponent(file)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch diff');
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
