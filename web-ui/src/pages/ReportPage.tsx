import React, { useEffect, useState } from 'react';
import type { Report } from '../types';
import { fetchReport, triggerAnalysis, fetchLauncherConfig, fetchModules, fetchCommitPreview, fetchDiff } from '../api';
import type { CommitPreview } from '../api';
import OverviewCard from '../components/OverviewCard';
import FileChangeList from '../components/FileChangeList';
import ImpactGraph from '../components/ImpactGraph';
import ReviewDetails from '../components/ReviewDetails';

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

function CrossModuleCard({ crossModuleImpacts }: { crossModuleImpacts: any[] }) {
  if (!crossModuleImpacts.length) return null;

  const riskColor = (risk: string) => {
    switch (risk) {
      case 'CRITICAL': return '#e74c3c';
      case 'HIGH': return '#e67e22';
      case 'MEDIUM': return '#f39c12';
      default: return '#2ecc71';
    }
  };

  return (
    <div style={{
      marginTop: 24, padding: 16, borderRadius: 8,
      border: '1px solid #e8e8e8', background: '#fafafa',
    }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>跨 Module 影响</h3>
      {crossModuleImpacts.map((item: any, idx: number) => (
        <div key={idx} style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '10px 14px', marginBottom: 8, borderRadius: 6,
          background: '#fff', border: '1px solid #eee',
          borderLeft: `3px solid ${riskColor(item.risk)}`,
        }}>
          <code style={{ fontWeight: 600, fontSize: 13 }}>{item.from_module}</code>
          <span style={{ color: '#999' }}>→</span>
          <code style={{ fontWeight: 600, fontSize: 13 }}>{item.to_module}</code>
          <span style={{
            fontSize: 11, padding: '1px 6px', borderRadius: 4, marginLeft: 'auto',
            backgroundColor: item.risk === 'CRITICAL' || item.risk === 'HIGH' ? '#ffeef0' : '#fef9e7',
            color: riskColor(item.risk),
          }}>{item.risk}</span>
          <span style={{ fontSize: 12, color: '#666' }}>{item.symbols.length} symbols</span>
        </div>
      ))}
    </div>
  );
}

function DiffPreview({ diffText }: { diffText: string }) {
  const lines = diffText.split('\n');
  const gutterWidth = String(lines.length).length * 8 + 16;
  return (
    <div style={{
      background: '#fafafa', border: '1px solid #e0e0e0', borderRadius: 8,
      marginTop: 4, overflowX: 'auto', maxHeight: 400, overflowY: 'auto',
    }}>
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
                <td style={{ padding: '0 4px', color: '#999', userSelect: 'none', width: 20, textAlign: 'center' }}>{prefix}</td>
                <td style={{ padding: '0 12px 0 4px', whiteSpace: 'pre-wrap', color: line.startsWith('+') ? '#22863a' : line.startsWith('-') ? '#cb2431' : '#24292e' }}>{line}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PreviewFileList({ preview, commitHash, repoPath }: { preview: CommitPreview; commitHash: string; repoPath: string }) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [diffText, setDiffText] = useState<string | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  useEffect(() => {
    if (!selectedFile) { setDiffText(null); return; }
    setDiffLoading(true);
    setDiffText(null);
    fetchDiff(commitHash, repoPath, selectedFile)
      .then((d) => setDiffText(d.diff))
      .catch(() => setDiffText('// Failed to load diff'))
      .finally(() => setDiffLoading(false));
  }, [selectedFile, commitHash, repoPath]);

  if (preview.changes.length === 0) {
    return (
      <div style={{ marginTop: 32 }}>
        <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Changed Files</h3>
        <p style={{ color: '#95a5a6', fontSize: 13 }}>无文件变更</p>
      </div>
    );
  }

  return (
    <div style={{ marginTop: 32 }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Changed Files ({preview.changes.length})</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
        <thead>
          <tr>
            <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid #eee', fontWeight: 600 }}>File</th>
            <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid #eee', fontWeight: 600, width: 60 }}>Added</th>
            <th style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid #eee', fontWeight: 600, width: 60 }}>Removed</th>
          </tr>
        </thead>
        <tbody>
          {preview.changes.map((c, idx) => (
            <React.Fragment key={idx}>
              <tr
                onClick={() => setSelectedFile(selectedFile === c.file ? null : c.file)}
                style={{ cursor: 'pointer', backgroundColor: selectedFile === c.file ? '#ebf5fb' : undefined }}
              >
                <td style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0' }}>
                  <code style={{ color: selectedFile === c.file ? '#3498db' : undefined }}>{c.file}</code>
                </td>
                <td style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0', color: '#27ae60' }}>+{c.added}</td>
                <td style={{ padding: '8px 12px', borderBottom: '1px solid #f0f0f0', color: '#e74c3c' }}>-{c.removed}</td>
              </tr>
              {selectedFile === c.file && (
                <tr>
                  <td colSpan={3} style={{ padding: '0 12px 12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#555' }}>Diff Preview</span>
                      <button onClick={() => setSelectedFile(null)} style={{
                        background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: '#999',
                      }}>&times;</button>
                    </div>
                    {diffLoading && <p style={{ color: '#95a5a6' }}>Loading diff...</p>}
                    {diffText && <DiffPreview diffText={diffText} />}
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ReportPage({ commitHash, repoPathParam = '' }: { commitHash: string; repoPathParam?: string }) {
  const [report, setReport] = useState<Report | null>(null);
  const [preview, setPreview] = useState<CommitPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [notAnalyzed, setNotAnalyzed] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [mode, setMode] = useState<AnalysisMode>('');
  const [repoPath, setRepoPath] = useState(repoPathParam || '.');
  const [crossModuleImpacts, setCrossModuleImpacts] = useState<any[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setNotAnalyzed(false);
    setPreview(null);
    setPreviewError(null);
    try {
      const [r, modulesData] = await Promise.all([
        fetchReport(commitHash),
        fetchModules(commitHash).catch(() => ({ cross_module_impacts: [], modules: [], file_modules: {} })),
      ]);
      setReport(r);
      setCrossModuleImpacts(modulesData.cross_module_impacts || []);
    } catch {
      // Report not found — load preview instead
      setNotAnalyzed(true);
      try {
        const p = await fetchCommitPreview(commitHash, repoPath);
        setPreview(p);
      } catch (e: any) {
        setPreviewError(e.message || '无法加载提交预览，请确认仓库路径正确');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!commitHash) return;
    if (!repoPathParam) {
      fetchLauncherConfig()
        .then((cfg) => setRepoPath(cfg.repo_path || '.'))
        .catch(() => {});
    }
    loadData();
  }, [commitHash, repoPathParam]);

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      const isQuick = mode === 'quick';
      await triggerAnalysis(commitHash, repoPath, isQuick);
      await loadData();
    } catch (e: any) {
      alert('分析失败: ' + (e.message || '未知错误'));
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div style={containerStyle}>
      {/* Toolbar */}
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
        {report && (
          <>
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
          </>
        )}
        <button
          onClick={handleAnalyze}
          disabled={analyzing || loading}
          style={{
            padding: '6px 20px', borderRadius: 6, border: 'none',
            fontSize: 13, fontWeight: 600, cursor: analyzing ? 'wait' : 'pointer',
            backgroundColor: analyzing ? '#ccc' : '#f39c12',
            color: '#fff', marginLeft: report ? 'auto' : undefined,
          }}
        >{analyzing ? '分析中...' : report ? '重新分析' : '分析此提交'}</button>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <p style={{ color: '#95a5a6', fontSize: 16 }}>Loading...</p>
        </div>
      )}

      {/* Not analyzed — show preview */}
      {!loading && notAnalyzed && (
        <>
          {preview && (
            <>
              <div style={{ marginBottom: 24 }}>
                <h2 style={{ fontSize: 18, margin: 0 }}>{preview.message || '(no message)'}</h2>
                <p style={{ fontSize: 13, color: '#95a5a6', marginTop: 4 }}>
                  <code>{preview.hash.slice(0, 12)}</code>
                  {preview.time && <><span style={{ margin: '0 8px' }}>&middot;</span>{preview.author}<span style={{ margin: '0 8px' }}>&middot;</span>{new Date(preview.time).toLocaleString('zh-CN')}</>}
                </p>
                {preview.body && <p style={{ fontSize: 13, color: '#7f8c8d', whiteSpace: 'pre-wrap' }}>{preview.body}</p>}
              </div>
              <PreviewFileList preview={preview} commitHash={commitHash} repoPath={repoPath} />
              <div style={{ marginTop: 24, textAlign: 'center', padding: 20, background: '#f8f9fa', borderRadius: 8, border: '1px solid #e8e8e8' }}>
                <p style={{ color: '#7f8c8d', marginBottom: 12 }}>点击上方按钮运行完整分析（影响链 + LLM 审查 + 跨 Module 分析）</p>
              </div>
            </>
          )}
          {!preview && (
            <div style={{ textAlign: 'center', padding: 60 }}>
              <h2 style={{ fontSize: 20, color: '#2c3e50', marginBottom: 12 }}>此提交尚未分析</h2>
              {previewError && (
                <p style={{ color: '#e74c3c', fontSize: 13, marginBottom: 16, background: '#ffeef0', padding: '8px 16px', borderRadius: 6, display: 'inline-block' }}>
                  {previewError}
                </p>
              )}
              <p style={{ color: '#95a5a6', marginBottom: 24 }}>
                分析后将展示代码变更影响范围、跨 Module 依赖分析和 LLM 审查意见。
              </p>
            </div>
          )}
        </>
      )}

      {/* Report content */}
      {report && (
        <>
          <OverviewCard report={report} />
          <ReviewDetails findings={report.findings} />
          <ImpactGraph
            impacts={report.impacts}
            findings={report.findings}
          />

          {crossModuleImpacts.length > 0 && <CrossModuleCard crossModuleImpacts={crossModuleImpacts} />}

          <FileChangeList
            changes={report.changes}
            fileAnalyses={report.file_analyses}
            commitHash={commitHash}
            repoPath={repoPath}
          />

          <div style={{ marginTop: 32 }}>
            <a href={`/api/reports/${report.commit_hash}/format`} style={{ color: '#3498db' }}>查看原始报告</a>
          </div>
        </>
      )}
    </div>
  );
}
