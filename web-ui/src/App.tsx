import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import ReportPage from './pages/ReportPage';
import LauncherPage from './pages/LauncherPage';
import CommitTimeline from './components/CommitTimeline';
import { fetchCommits, triggerAnalysis, fetchLauncherConfig, saveLauncherConfig, triggerGerritAnalysis } from './api';
import type { CommitNode, BranchInfo } from './api';

const containerStyle: React.CSSProperties = {
  maxWidth: 800,
  margin: '0 auto',
  padding: 24,
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
};

function TimelineView() {
  const loadSeq = useRef(0);
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
  const [branchQuery, setBranchQuery] = useState('');
  const [gerritUrl, setGerritUrl] = useState('');
  const [gerritLoading, setGerritLoading] = useState(false);
  const [gerritError, setGerritError] = useState<string | null>(null);

  const isDetachedHeadPseudoBranch = (name: string) =>
    /^\(HEAD detached (at|from) .+\)$/.test(name.trim()) || /^\(no branch\)$/.test(name.trim());

  const normalizeBranchSelection = (name: string) =>
    isDetachedHeadPseudoBranch(name) ? '' : name;

  const getEffectiveBranch = (p: string) => perRepoBranches[p] || globalBranch || '';

  const applyLauncherConfig = useCallback((cfg: any) => {
    const reposList = cfg.repos || [];
    const normalizedGlobalBranch = normalizeBranchSelection(cfg.global_branch || '');
    const normalizedPerRepoBranches = Object.fromEntries(
      Object.entries(cfg.per_repo_branches || {}).map(([k, v]) => [k, normalizeBranchSelection(v as string)])
    ) as Record<string, string>;

    setRepos(reposList);
    setGlobalBranch(normalizedGlobalBranch);
    setPerRepoBranches(normalizedPerRepoBranches);

    return { normalizedGlobalBranch, normalizedPerRepoBranches, reposList };
  }, []);

  const loadCommits = useCallback((path: string, branch: string) => {
    if (!path) return;
    const seq = ++loadSeq.current;
    setLoading(true);
    setError(null);
    setRepoName('');
    setCommits([]);
    setBranches([]);
    fetchCommits(path, branch)
      .then((data) => {
        if (seq !== loadSeq.current) return;
        setCommits(data.commits);
        setBranches(data.branches);
        setRepoName(data.repo_name);
      })
      .catch((e) => {
        if (seq !== loadSeq.current) return;
        const message = e.message || 'Not a git repository or no commits found.';
        if (branch && /invalid branch/i.test(message)) {
          fetchLauncherConfig()
            .then(async (cfg) => {
              const updatedPerRepoBranches = { ...(cfg.per_repo_branches || {}) };
              delete updatedPerRepoBranches[path];
              await saveLauncherConfig({
                ...cfg,
                global_branch: '',
                per_repo_branches: updatedPerRepoBranches,
              } as any);
              if (path === repoPath) {
                setGlobalBranch('');
                setPerRepoBranches(updatedPerRepoBranches);
              }
            })
            .catch(() => {});
          loadCommits(path, '');
          return;
        }
        setError(message);
        setCommits([]);
        setBranches([]);
      })
      .finally(() => {
        if (seq === loadSeq.current) setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchLauncherConfig()
      .then((cfg) => {
        // In multi-repo mode, default to first repo when no current_repo set
        let path = cfg.current_repo || cfg.repo_path || '.';
        const { normalizedGlobalBranch, normalizedPerRepoBranches, reposList } = applyLauncherConfig(cfg);
        if (reposList.length > 1 && !cfg.current_repo) {
          path = reposList[0];
          saveLauncherConfig({ ...cfg, current_repo: path } as any).catch(() => {});
        }
        setRepoPath(path);
        const pb = normalizedPerRepoBranches[path];
        const savedBranch = pb || normalizedGlobalBranch || '';
        if (normalizedGlobalBranch !== (cfg.global_branch || '') ||
            JSON.stringify(normalizedPerRepoBranches) !== JSON.stringify(cfg.per_repo_branches || {})) {
          saveLauncherConfig({
            ...cfg,
            global_branch: normalizedGlobalBranch,
            per_repo_branches: normalizedPerRepoBranches,
          } as any).catch(() => {});
        }
        loadCommits(path, savedBranch);
      })
      .catch(() => loadCommits('.', ''));
  }, []);

  const handleRepoChange = async (path: string) => {
    if (!path || path === repoPath) return;
    setRepoPath(path);
    setCommits([]);
    setBranches([]);
    setRepoName('');
    setError(null);
    try {
      const cfg = await fetchLauncherConfig();
      const nextConfig = {
        ...cfg,
        current_repo: path,
      };
      await saveLauncherConfig(nextConfig as any);
      const refreshed = await fetchLauncherConfig();
      const { normalizedGlobalBranch, normalizedPerRepoBranches } = applyLauncherConfig(refreshed);
      const branch = normalizedPerRepoBranches[path] || normalizedGlobalBranch || '';
      loadCommits(path, branch);
      return;
    } catch { /* ignore */ }
    loadCommits(path, getEffectiveBranch(path));
  };

  const handleGlobalBranchChange = async (branch: string) => {
    branch = normalizeBranchSelection(branch);
    setGlobalBranch(branch);
    setPerRepoBranches({});
    try {
      const cfg = await fetchLauncherConfig();
      await saveLauncherConfig({ ...cfg, global_branch: branch, per_repo_branches: {} } as any);
    } catch { /* ignore */ }
    loadCommits(repoPath, branch);
  };

  const handlePerRepoBranchChange = async (path: string, branch: string) => {
    branch = normalizeBranchSelection(branch);
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

  const handleGerritAnalyze = async () => {
    if (!gerritUrl.trim()) return;
    setGerritLoading(true);
    setGerritError(null);
    try {
      const result = await triggerGerritAnalysis(gerritUrl.trim());
      window.location.href = result.report_url;
    } catch (e: any) {
      setGerritError(e.message || 'Gerrit analysis failed');
    } finally {
      setGerritLoading(false);
    }
  };

  const isMultiRepo = repos.length > 1;
  const selectedBranch = useMemo(() => {
    const candidate = getEffectiveBranch(repoPath);
    return candidate && branches.some((b) => b.name === candidate) ? candidate : '';
  }, [branches, repoPath, globalBranch, perRepoBranches]);
  const filteredBranches = useMemo(() => {
    const q = branchQuery.trim().toLowerCase();
    if (!q) return branches;
    const tokens = q.split(/\s+/).filter(Boolean);
    return branches.filter((b) => {
      const displayName = b.name.startsWith('remotes/') ? b.name.slice(8) : b.name;
      const haystack = `${b.name} ${displayName}`.toLowerCase();
      return tokens.every((t) => haystack.includes(t));
    });
  }, [branches, branchQuery]);
  const groupedRepos = useMemo(() => {
    const groups = new Map<string, { title: string; items: { path: string; name: string }[] }>();

    for (const repo of repos) {
      const normalized = repo.replace(/\\/g, '/');
      const slash = normalized.lastIndexOf('/');
      const parentPath = slash > 0 ? normalized.slice(0, slash) : '';
      const parentName = parentPath ? (parentPath.split('/').pop() || parentPath) : '其他';
      const repoName = slash >= 0 ? (normalized.slice(slash + 1) || normalized) : normalized;
      const key = parentPath || `__${parentName}`;
      const group = groups.get(key) || { title: parentName, items: [] };
      group.items.push({ path: repo, name: repoName });
      groups.set(key, group);
    }

    return Array.from(groups.entries()).map(([key, value]) => ({ key, ...value }));
  }, [repos]);

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

      {/* Gerrit URL input */}
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        <input
          value={gerritUrl}
          onChange={(e) => setGerritUrl(e.target.value)}
          placeholder="Gerrit 变更 URL..."
          onKeyDown={(e) => e.key === 'Enter' && handleGerritAnalyze()}
          style={{
            flex: 1, padding: '6px 10px', borderRadius: 4, border: '1px solid #ddd',
            fontSize: 13, fontFamily: 'monospace',
          }}
        />
        <button
          onClick={handleGerritAnalyze}
          disabled={gerritLoading}
          style={{
            padding: '6px 16px', borderRadius: 4, border: 'none', fontSize: 13,
            fontWeight: 600, color: '#fff', backgroundColor: gerritLoading ? '#95a5a6' : '#27ae60',
            cursor: 'pointer', whiteSpace: 'nowrap',
          }}
        >
          {gerritLoading ? '分析中...' : 'Gerrit 分析'}
        </button>
      </div>
      {gerritError && (
        <div style={{ marginBottom: 12, padding: '8px 12px', background: '#ffeef0', borderRadius: 6, fontSize: 13, color: '#e74c3c' }}>
          {gerritError}
        </div>
      )}

      <div style={{ display: 'flex', gap: 20 }}>
        {/* Left sidebar: global branch + repo tree */}
        {isMultiRepo && (
          <div style={{
            width: 260, flexShrink: 0,
            padding: 12, borderRadius: 8, border: '1px solid #e8e8e8',
            background: '#fafafa',
            display: 'flex',
            flexDirection: 'column',
            maxHeight: 'calc(100vh - 220px)',
          }}>
            {/* Global branch selector */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#7f8c8d', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 6 }}>
                全局分支
              </div>
              <input
                value={branchQuery}
                onChange={(e) => setBranchQuery(e.target.value)}
                placeholder="输入关键词过滤分支"
                style={{
                  width: '100%',
                  padding: '4px 10px',
                  borderRadius: 4,
                  border: '1px solid #ddd',
                  fontSize: 13,
                  marginBottom: 6,
                  boxSizing: 'border-box',
                }}
              />
              <div style={{ position: 'relative' }}>
                <button
                  onClick={() => setBranchMenuOpen(!branchMenuOpen)}
                  style={{
                    width: '100%', padding: '5px 8px', borderRadius: 4,
                    border: '1px solid #ddd', fontSize: 13, background: '#fff',
                    cursor: 'pointer', textAlign: 'left',
                    color: selectedBranch ? '#333' : '#999',
                  }}
                >
                  {selectedBranch ? (selectedBranch.startsWith('remotes/') ? selectedBranch.slice(8) : selectedBranch) : '选择分支'}
                </button>
                {branchMenuOpen && (
                  <div style={{
                    position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 10,
                    background: '#fff', border: '1px solid #ddd', borderRadius: 4,
                    maxHeight: 200, overflow: 'auto', marginTop: 2,
                  }}>
                    {filteredBranches
                      .filter(b => !b.name.startsWith('HEAD') && !isDetachedHeadPseudoBranch(b.name))
                      .map(b => {
                        const displayName = b.name.startsWith('remotes/') ? b.name.slice(8) : b.name;
                        const isActive = b.name === selectedBranch;
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

            <div style={{ fontSize: 12, fontWeight: 700, color: '#7f8c8d', textTransform: 'uppercase', letterSpacing: 1, marginBottom: 8 }}>
              全体仓库
            </div>
            <div style={{ overflowY: 'auto', paddingRight: 4 }}>
              {groupedRepos.map((group) => (
                <div key={group.key} style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: '#7f8c8d', marginBottom: 4 }}>
                    {group.title}
                  </div>
                  {group.items.map((item) => {
                    const isActive = item.path === repoPath;
                    const effective = getEffectiveBranch(item.path);
                    return (
                      <div key={item.path} style={{ marginBottom: 2 }}>
                        <div
                          onClick={() => handleRepoChange(item.path)}
                          style={{
                            padding: '5px 10px 5px 16px', cursor: 'pointer', fontSize: 13,
                            borderRadius: 4,
                            backgroundColor: isActive ? '#d4e6f1' : 'transparent',
                            color: isActive ? '#2980b9' : '#333',
                            fontWeight: isActive ? 600 : 400,
                          }}
                        >
                          {item.name}
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
              ))}
            </div>
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
                .filter(b => !b.name.startsWith('HEAD') && !isDetachedHeadPseudoBranch(b.name))
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
