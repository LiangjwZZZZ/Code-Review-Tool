import { useEffect, useState, useCallback, useRef } from 'react';
import ReportPage from './pages/ReportPage';
import LauncherPage from './pages/LauncherPage';
import CommitTimeline from './components/CommitTimeline';
import { fetchCommits, triggerAnalysis, fetchLauncherConfig, saveLauncherConfig } from './api';
import type { CommitNode, BranchInfo } from './api';

const containerStyle: React.CSSProperties = {
  maxWidth: 800,
  margin: '0 auto',
  padding: 24,
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
};

function TimelineView() {
  const [commits, setCommits] = useState<CommitNode[]>([]);
  const [branches, setBranches] = useState<BranchInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState<Set<string>>(new Set());
  const [repoName, setRepoName] = useState('');
  const [selectedBranch, setSelectedBranch] = useState('');
  const [repoPath, setRepoPath] = useState('.');
  const [repos, setRepos] = useState<string[]>([]);

  const loadCommits = useCallback((path: string, branch: string) => {
    if (!path) return;
    setLoading(true);
    setError(null);
    setRepoName('');
    fetchCommits(path, branch)
      .then((data) => {
        setCommits(data.commits);
        setBranches(data.branches);
        setRepoName(data.repo_name);
      })
      .catch((e) => {
        setError(e.message || 'Not a git repository or no commits found.');
        setCommits([]);
        setBranches([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchLauncherConfig()
      .then((cfg) => {
        const path = cfg.repo_path || '.';
        setRepoPath(path);
        setRepos(cfg.repos || []);
        loadCommits(path, selectedBranch);
      })
      .catch(() => loadCommits('.', selectedBranch));
  }, []);

  const handleRepoChange = (path: string) => {
    if (!path || path === repoPath) return;
    setRepoPath(path);
    // Persist to config so ReportPage uses the same path
    saveLauncherConfig({ repo_path: path } as any).catch(() => {});
    loadCommits(path, selectedBranch);
  };

  const handleAddRepo = async (path: string) => {
    if (repos.includes(path)) return;
    const updated = [...repos, path];
    setRepos(updated);
    await saveLauncherConfig({ repo_path: path, repos: updated } as any).catch(() => {});
    handleRepoChange(path);
  };

  const handleRemoveRepo = async (path: string) => {
    const updated = repos.filter(r => r !== path);
    setRepos(updated);
    await saveLauncherConfig({ repos: updated } as any).catch(() => {});
  };

  const handleBranchChange = (branch: string) => {
    setSelectedBranch(branch);
    loadCommits(repoPath, branch);
  };

  const handleAnalyze = async (hash: string) => {
    setAnalyzing((prev) => new Set(prev).add(hash));
    try {
      await triggerAnalysis(hash, repoPath, false);
      loadCommits(selectedBranch, repoPath);
    } catch (e: any) {
      alert('Analysis failed: ' + (e.message || 'unknown error'));
    } finally {
      setAnalyzing((prev) => {
        const next = new Set(prev);
        next.delete(hash);
        return next;
      });
    }
  };

  const handleViewReport = (hash: string) => {
    window.location.href = `/report/${hash}?repo=${encodeURIComponent(repoPath)}`;
  };

  return (
    <div style={containerStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>
          {repoName ? `${repoName} - Commit Timeline` : 'Commit Timeline'}
        </h1>
        <div style={{ display: 'flex', gap: 8 }}>
          <a href="/settings" style={{
            color: '#fff', backgroundColor: '#3498db', textDecoration: 'none',
            padding: '8px 18px', borderRadius: 6, fontSize: 14, fontWeight: 600,
          }}>设置</a>
        </div>
      </div>

      {/* Repo selector — like branch selector */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
        padding: '8px 12px', background: '#f8f9fa', borderRadius: 6,
        border: '1px solid #e8e8e8', flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: 13, color: '#7f8c8d', fontWeight: 600 }}>仓库:</span>
        <select
          value={repoPath}
          onChange={(e) => handleRepoChange(e.target.value)}
          style={{
            flex: 1, minWidth: 200, padding: '6px 10px',
            borderRadius: 4, border: '1px solid #ddd',
            fontSize: 13, fontFamily: 'monospace',
          }}
        >
          <option value=".">.</option>
          {repos.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <button
          onClick={() => {
            const name = prompt('输入仓库路径:');
            if (name) handleAddRepo(name.trim());
          }}
          style={{
            padding: '6px 14px', borderRadius: 4, border: '1px solid #ddd',
            background: '#fff', cursor: 'pointer', fontSize: 12, color: '#555',
          }}
        >+ 添加</button>
        {repos.length > 0 && (
          <button
            onClick={() => {
              if (confirm(`从列表中移除 "${repoPath}"？`)) handleRemoveRepo(repoPath);
            }}
            style={{
              padding: '6px 14px', borderRadius: 4, border: '1px solid #ddd',
              background: '#fff', cursor: 'pointer', fontSize: 12, color: '#e74c3c',
            }}
          >删除</button>
        )}
      </div>

      {error && (
        <div style={{ padding: 20, background: '#ffeef0', borderRadius: 8, border: '1px solid #e8e8e8', marginBottom: 16 }}>
          <p style={{ color: '#e74c3c', fontSize: 13 }}>{error}</p>
        </div>
      )}

      <p style={{ fontSize: 13, color: '#7f8c8d', marginBottom: 20 }}>
        {loading ? 'Loading commits...' : `Showing ${commits.length} commit(s)`}
      </p>
      {loading && <p style={{ color: '#95a5a6' }}>Loading...</p>}
      {!loading && commits.length === 0 && !error && (
        <p style={{ color: '#95a5a6' }}>No commits found.</p>
      )}
      {!loading && commits.length > 0 && (
        <CommitTimeline
          commits={commits}
          branches={branches}
          selectedBranch={selectedBranch}
          onBranchChange={handleBranchChange}
          onViewReport={handleViewReport}
          onAnalyze={handleAnalyze}
          analyzing={analyzing}
        />
      )}
    </div>
  );
}

function App() {
  const url = window.location;
  const path = url.pathname;
  if (path.startsWith('/report/')) {
    const hash = path.replace('/report/', '').split('?')[0];
    const params = new URLSearchParams(url.search);
    return <ReportPage commitHash={hash} repoPathParam={params.get('repo') || ''} />;
  }
  if (path === '/timeline') {
    return <TimelineView />;
  }
  return <LauncherPage />;
}

export default App;
