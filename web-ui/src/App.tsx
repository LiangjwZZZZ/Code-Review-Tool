import { useEffect, useState, useCallback, useRef } from 'react';
import ReportPage from './pages/ReportPage';
import LauncherPage from './pages/LauncherPage';
import CommitTimeline from './components/CommitTimeline';
import { fetchCommits, triggerAnalysis, fetchLauncherConfig } from './api';
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
  const repoPathRef = useRef('.');

  const loadCommits = useCallback((branch: string, repo?: string) => {
    const path = repo || repoPathRef.current;
    setLoading(true);
    fetchCommits(path, branch)
      .then((data) => {
        setCommits(data.commits);
        setBranches(data.branches);
        setRepoName(data.repo_name);
      })
      .catch(() => setError('Not a git repository or no commits found.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchLauncherConfig()
      .then((cfg) => {
        const path = cfg.repo_path || '.';
        repoPathRef.current = path;
        loadCommits(selectedBranch, path);
      })
      .catch(() => loadCommits(selectedBranch, '.'));
  }, []); // only on mount — loads config then commits once

  const handleBranchChange = (branch: string) => {
    setSelectedBranch(branch);
    loadCommits(branch, repoPathRef.current);
  };

  const handleAnalyze = async (hash: string) => {
    setAnalyzing((prev) => new Set(prev).add(hash));
    try {
      await triggerAnalysis(hash, repoPathRef.current, false);
      loadCommits(selectedBranch, repoPathRef.current);
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
    window.location.href = `/report/${hash}`;
  };

  if (error) {
    return (
      <div style={containerStyle}>
        <h1 style={{ fontSize: 22 }}>Review Timeline</h1>
        <p style={{ color: '#e74c3c' }}>{error}</p>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>
          {repoName ? `${repoName} - Commit Timeline` : 'Commit Timeline'}
        </h1>
        <a href="/settings" style={{
          color: '#fff', backgroundColor: '#3498db', textDecoration: 'none',
          padding: '8px 18px', borderRadius: 6, fontSize: 14, fontWeight: 600,
        }}>⚙ 设置</a>
      </div>
      <p style={{ fontSize: 13, color: '#7f8c8d', marginBottom: 20 }}>
        {loading ? 'Loading commits...' : `Showing ${commits.length} commit(s)`}
      </p>
      {loading && <p style={{ color: '#95a5a6' }}>Loading...</p>}
      {!loading && commits.length === 0 && (
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
  const path = window.location.pathname;
  if (path.startsWith('/report/')) {
    const hash = path.replace('/report/', '');
    return <ReportPage commitHash={hash} />;
  }
  if (path === '/timeline') {
    return <TimelineView />;
  }
  return <LauncherPage />;
}

export default App;
