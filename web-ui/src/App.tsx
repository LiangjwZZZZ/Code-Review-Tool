import { useEffect, useState, useCallback } from 'react';
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
  const [globalBranch, setGlobalBranch] = useState('');
  const [perRepoBranches, setPerRepoBranches] = useState<Record<string, string>>({});
  const [repoPath, setRepoPath] = useState('.');
  const [repos, setRepos] = useState<string[]>([]);
  const [branchMenuOpen, setBranchMenuOpen] = useState(false);

  const getEffectiveBranch = (p: string) => perRepoBranches[p] || globalBranch || '';

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
        const reposList = cfg.repos || [];
        setRepos(reposList);
        // In multi-repo mode, default to first repo when no current_repo set
        let path = cfg.current_repo || cfg.repo_path || '.';
        if (reposList.length > 1 && !cfg.current_repo) {
          path = reposList[0];
          saveLauncherConfig({ ...cfg, current_repo: path } as any).catch(() => {});
        }
        setRepoPath(path);
        setGlobalBranch(cfg.global_branch || '');
        setPerRepoBranches(cfg.per_repo_branches || {});
        const pb = (cfg.per_repo_branches || {})[path];
        const savedBranch = pb || cfg.global_branch || '';
        loadCommits(path, savedBranch);
      })
      .catch(() => loadCommits('.', ''));
  }, []);

  const handleRepoChange = async (path: string) => {
    if (!path || path === repoPath) return;
    setRepoPath(path);
    try {
      const cfg = await fetchLauncherConfig();
      await saveLauncherConfig({ ...cfg, current_repo: path } as any);
    } catch { /* ignore */ }
    loadCommits(path, getEffectiveBranch(path));
  };

  const handleGlobalBranchChange = async (branch: string) => {
    setGlobalBranch(branch);
    setPerRepoBranches({});
    try {
      const cfg = await fetchLauncherConfig();
      await saveLauncherConfig({ ...cfg, global_branch: branch, per_repo_branches: {} } as any);
    } catch { /* ignore */ }
    loadCommits(repoPath, branch);
  };

  const handlePerRepoBranchChange = async (path: string, branch: string) => {
    const updated = { ...perRepoBranches, [path]: branch };
    setPerRepoBranches(updated);
    try {
      const cfg = await fetchLauncherConfig();
      await saveLauncherConfig({ ...cfg, per_repo_branches: updated } as any);
    } catch { /* ignore */ }
    if (path === repoPath) {
      loadCommits(path, branch);
    }
  };

  const handleAnalyze = async (hash: string) => {
    setAnalyzing((prev) => new Set(prev).add(hash));
    try {
      await triggerAnalysis(hash, repoPath, false);
      loadCommits(repoPath, getEffectiveBranch(repoPath));
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

  const isMultiRepo = repos.length > 1;
  const rootPath = isMultiRepo ? repos[0].substring(0, repos[0].lastIndexOf('/')) : '';
  const rootName = rootPath ? rootPath.split('/').pop() || rootPath : '';

  return (
    <div style={{ ...containerStyle, maxWidth: isMultiRepo ? 1200 : 800 }}>
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

      <div style={{ display: 'flex', gap: 20 }}>
        {/* Left sidebar: global branch + repo tree */}
        {isMultiRepo && (
          <div style={{
            width: 260, flexShrink: 0,
            padding: 12, borderRadius: 8, border: '1px solid #e8e8e8',
            background: '#fafafa', height: 'fit-content',
          }}>
            {/* Global branch selector */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#7f8c8d', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
                全局分支
              </div>
              <div style={{ position: 'relative' }}>
                <button
                  onClick={() => setBranchMenuOpen(!branchMenuOpen)}
                  style={{
                    width: '100%', padding: '5px 8px', borderRadius: 4,
                    border: '1px solid #ddd', fontSize: 13, background: '#fff',
                    cursor: 'pointer', textAlign: 'left',
                    color: globalBranch ? '#333' : '#999',
                  }}
                >
                  {globalBranch ? (globalBranch.startsWith('remotes/') ? globalBranch.slice(8) : globalBranch) : '选择分支'}
                </button>
                {branchMenuOpen && (
                  <div style={{
                    position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10,
                    background: '#fff', border: '1px solid #ddd', borderRadius: 4,
                    maxHeight: 200, overflow: 'auto', marginTop: 2,
                  }}>
                    {branches
                      .filter(b => !b.name.startsWith('HEAD'))
                      .map(b => {
                        const displayName = b.name.startsWith('remotes/') ? b.name.slice(8) : b.name;
                        const isActive = b.name === globalBranch;
                        return (
                          <div
                            key={b.name}
                            onClick={() => {
                              handleGlobalBranchChange(b.name);
                              setBranchMenuOpen(false);
                            }}
                            style={{
                              padding: '5px 10px', cursor: 'pointer', fontSize: 13,
                              background: isActive ? '#e8f4fd' : 'transparent',
                              color: isActive ? '#2980b9' : '#333',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = isActive ? '#d0e8f7' : '#f5f5f5')}
                            onMouseLeave={(e) => {
                              e.currentTarget.style.background = isActive ? '#e8f4fd' : 'transparent';
                            }}
                          >
                            {displayName}
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
              {/* Overlay to close menu on outside click */}
              {branchMenuOpen && (
                <div
                  style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9 }}
                  onClick={() => setBranchMenuOpen(false)}
                />
              )}
            </div>

            {/* Repo tree */}
            <div style={{ fontSize: 12, fontWeight: 700, color: '#7f8c8d', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
              {rootName}
            </div>
            {repos.map((r) => {
              const rel = r.replace(rootPath + '/', '');
              const isActive = r === repoPath;
              const effective = getEffectiveBranch(r);
              return (
                <div key={r} style={{ marginBottom: 2 }}>
                  {/* Repo name */}
                  <div
                    onClick={() => handleRepoChange(r)}
                    style={{
                      padding: '5px 10px 5px 16px', cursor: 'pointer', fontSize: 13,
                      borderRadius: 4,
                      backgroundColor: isActive ? '#d4e6f1' : 'transparent',
                      color: isActive ? '#2980b9' : '#333',
                      fontWeight: isActive ? 600 : 400,
                    }}
                  >
                    {rel}
                    {effective && (
                      <span style={{
                        marginLeft: 6, fontSize: 11, color: '#7f8c8d',
                        backgroundColor: '#f0f0f0', padding: '1px 6px', borderRadius: 3,
                      }}>{effective}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Main content */}
        <div style={{ flex: 1, minWidth: 0 }}>

          {/* Per-repo branch selector */}
          {branches.length > 0 && (
            <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, color: '#7f8c8d', fontWeight: 600 }}>分支:</span>
              <select
                value={getEffectiveBranch(repoPath)}
                onChange={(e) => handlePerRepoBranchChange(repoPath, e.target.value)}
                style={{
                  padding: '4px 10px', borderRadius: 4, border: '1px solid #ddd',
                  fontSize: 13, fontWeight: 500,
                }}
              >
                <option value="">所有分支</option>
                {branches
                  .filter(b => !b.name.startsWith('HEAD'))
                  .map((b) => (
                    <option key={b.name} value={b.name}>
                      {b.name.startsWith('remotes/') ? b.name.slice(8) : b.name}
                    </option>
                  ))}
              </select>
              <span style={{ fontSize: 12, color: '#95a5a6' }}>
                {commits.length} commit(s)
              </span>
            </div>
          )}

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
          selectedBranch={getEffectiveBranch(repoPath)}
          onViewReport={handleViewReport}
          onAnalyze={handleAnalyze}
          analyzing={analyzing}
        />
      )}
        </div>
      </div>
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
