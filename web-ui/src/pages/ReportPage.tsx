import { useEffect, useState } from 'react';
import type { Report } from '../types';
import { fetchReport, triggerAnalysis, fetchLauncherConfig, fetchDiff } from '../api';
import OverviewCard from '../components/OverviewCard';
import FileChangeList from '../components/FileChangeList';
import ImpactGraph from '../components/ImpactGraph';
import ReviewDetails from '../components/ReviewDetails';
import CommunityGraph from '../components/CommunityGraph';

const containerStyle: React.CSSProperties = {
  maxWidth: 1000,
  margin: '0 auto',
  padding: 24,
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
};

type AnalysisMode = '' | 'quick';

const MODE_BTN: Record<AnalysisMode, { label: string; desc: string }> = {
  '': { label: '默认', desc: '包含 LLM 分析' },
  quick: { label: '快速', desc: '仅影响分析，跳过 LLM' },
};

export default function ReportPage({ commitHash }: { commitHash: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [mode, setMode] = useState<AnalysisMode>('');
  const [repoPath, setRepoPath] = useState('.');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [diffText, setDiffText] = useState<string | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  useEffect(() => {
    if (!commitHash) return;
    fetchReport(commitHash)
      .then(setReport)
      .catch(() => setError('Report not found.'));
    fetchLauncherConfig()
      .then((cfg) => setRepoPath(cfg.repo_path || '.'))
      .catch(() => {});
  }, [commitHash]);

  useEffect(() => {
    if (!selectedFile || !commitHash) {
      setDiffText(null);
      return;
    }
    setDiffLoading(true);
    setDiffText(null);
    fetchDiff(commitHash, repoPath, selectedFile)
      .then((data) => setDiffText(data.diff))
      .catch(() => setDiffText('// Failed to load diff'))
      .finally(() => setDiffLoading(false));
  }, [selectedFile, commitHash, repoPath]);

  const handleReanalyze = async () => {
    setAnalyzing(true);
    setSelectedFile(null);
    try {
      const isQuick = mode === 'quick';
      await triggerAnalysis(commitHash, repoPath, isQuick);
      const newReport = await fetchReport(commitHash);
      setReport(newReport);
    } catch (e: any) {
      alert('分析失败: ' + (e.message || '未知错误'));
    } finally {
      setAnalyzing(false);
    }
  };

  function renderDiff(diff: string) {
    const lines = diff.split('\n');
    const gutterWidth = String(lines.length).length * 8 + 16;

    return (
      <div style={{
        background: '#fafafa', border: '1px solid #e0e0e0', borderRadius: 8,
        marginTop: 12, overflow: 'hidden',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 14px', background: '#f0f0f0',
          borderBottom: '1px solid #e0e0e0', fontSize: 13, fontWeight: 600, color: '#555',
        }}>
          <span style={{ flex: 1 }}>{selectedFile}</span>
          <button
            onClick={() => setSelectedFile(null)}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              fontSize: 16, color: '#999', padding: '0 4px',
            }}
          >&times;</button>
        </div>
        <div style={{ overflowX: 'auto', maxHeight: 500, overflowY: 'auto' }}>
          <table style={{ borderCollapse: 'collapse', width: '100%', fontFamily: '"SF Mono", "Fira Code", monospace', fontSize: 12, lineHeight: 1.6 }}>
            <tbody>
              {lines.map((line, i) => {
                let bg = '';
                let prefix = ' ';
                if (line.startsWith('+')) { bg = '#e6ffed'; prefix = '+'; }
                else if (line.startsWith('-')) { bg = '#ffeef0'; prefix = '-'; }
                else if (line.startsWith('@')) { bg = '#f0f0f0'; prefix = '@'; }
                else if (line.startsWith('diff --git') || line.startsWith('index ') || line.startsWith('--- ') || line.startsWith('+++ ')) { bg = '#f8f8f8'; }

                return (
                  <tr key={i} style={{ backgroundColor: bg }}>
                    <td style={{
                      width: gutterWidth, minWidth: gutterWidth,
                      padding: '0 8px', textAlign: 'right', color: '#999',
                      borderRight: '1px solid #e0e0e0', userSelect: 'none',
                      background: '#fafafa',
                    }}>{i + 1}</td>
                    <td style={{
                      padding: '0 4px', color: '#999', userSelect: 'none',
                      width: 20, textAlign: 'center',
                    }}>{prefix}</td>
                    <td style={{ padding: '0 12px 0 4px', whiteSpace: 'pre-wrap', color: line.startsWith('+') ? '#22863a' : line.startsWith('-') ? '#cb2431' : '#24292e' }}>{line}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={containerStyle}>
        <h1>Review Tool</h1>
        <p style={{ color: '#e74c3c' }}>{error}</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div style={containerStyle}>
        <h1>Review Tool</h1>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* Re-analyze toolbar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12,
        padding: '12px 16px', background: '#f8f9fa', borderRadius: 8,
        border: '1px solid #e8e8e8', marginBottom: 20, flexWrap: 'wrap',
      }}>
        <a href="/timeline" style={{
          padding: '6px 16px', borderRadius: 6, border: 'none',
          fontSize: 13, fontWeight: 600, cursor: 'pointer',
          backgroundColor: '#3498db', color: '#fff', textDecoration: 'none',
        }}>← 时间线</a>
        <span style={{ fontSize: 13, fontWeight: 600, color: '#555', whiteSpace: 'nowrap' }}>重新分析</span>
        {(['', 'quick'] as AnalysisMode[]).map((m) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            style={{
              padding: '6px 16px', borderRadius: 6, border: '1px solid',
              fontSize: 13, fontWeight: 500, cursor: 'pointer',
              borderColor: mode === m ? '#3498db' : '#ddd',
              backgroundColor: mode === m ? '#ebf5fb' : '#fff',
              color: mode === m ? '#3498db' : '#555',
            }}
          >{MODE_BTN[m].label}</button>
        ))}
        <button
          onClick={handleReanalyze}
          disabled={analyzing}
          style={{
            padding: '6px 20px', borderRadius: 6, border: 'none',
            fontSize: 13, fontWeight: 600, cursor: analyzing ? 'wait' : 'pointer',
            backgroundColor: analyzing ? '#ccc' : '#f39c12',
            color: '#fff', marginLeft: 'auto',
          }}
        >{analyzing ? '分析中...' : '重新分析'}</button>
      </div>

      <OverviewCard report={report} />
      <ReviewDetails findings={report.findings} />
      <ImpactGraph impacts={report.impacts} />
      {report.impacts.length > 1 && <CommunityGraph impacts={report.impacts} />}
      <FileChangeList
        changes={report.changes}
        selectedFile={selectedFile}
        onSelectFile={(f) => setSelectedFile(f)}
      />

      {diffLoading && <p style={{ color: '#95a5a6', marginTop: 12 }}>Loading diff...</p>}
      {diffText && renderDiff(diffText)}

      <div style={{ marginTop: 32 }}>
        <a href={`/api/reports/${report.commit_hash}/format`} style={{ color: '#3498db' }}>View raw report</a>
      </div>
    </div>
  );
}
