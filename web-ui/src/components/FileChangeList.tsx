import { useState } from 'react';
import type { FileAnalysis, DiffChange, ImpactItem, ReviewFinding } from '../types';
import { triggerFileAnalysis } from '../api';

const tableStyle: React.CSSProperties = {
  width: '100%', borderCollapse: 'collapse', fontSize: 14,
};

const thStyle: React.CSSProperties = {
  textAlign: 'left', padding: '8px 12px', borderBottom: '2px solid #eee', fontWeight: 600,
};

const tdStyle: React.CSSProperties = {
  padding: '8px 12px', borderBottom: '1px solid #f0f0f0',
};

const DEFAULT_SHOW = 10;

function ModuleTag({ module }: { module: string }) {
  if (!module) return null;
  const colors: Record<string, string> = {
    ':app': '#3498db',
    ':lib': '#9b59b6',
    ':sdk': '#e67e22',
  };
  const color = Object.entries(colors).find(([k]) => module.startsWith(k))?.[1] || '#95a5a6';
  return (
    <span style={{
      display: 'inline-block', padding: '1px 8px', borderRadius: 10,
      fontSize: 11, fontWeight: 600, color: '#fff', backgroundColor: color,
      marginLeft: 8, verticalAlign: 'middle',
    }}>{module}</span>
  );
}

function DiffPreview({ diffText }: { diffText: string }) {
  const lines = diffText.split('\n');
  const gutterWidth = String(lines.length).length * 8 + 16;

  return (
    <div style={{
      background: '#fafafa', border: '1px solid #e0e0e0', borderRadius: 8,
      marginTop: 4, overflow: 'hidden', maxHeight: 400, overflowY: 'auto',
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
  );
}

function ImpactSummary({ impacts }: { impacts: ImpactItem[] }) {
  if (!impacts.length) return <p style={{ color: '#95a5a6', fontSize: 13, marginTop: 8 }}>无影响链数据</p>;
  return (
    <div style={{ marginTop: 12 }}>
      <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, color: '#555' }}>影响链</h4>
      {impacts.map((imp, idx) => (
        <div key={idx} style={{
          padding: '8px 12px', marginBottom: 6, borderRadius: 6,
          border: '1px solid #eee', fontSize: 13,
          borderLeft: `3px solid ${imp.risk === 'CRITICAL' || imp.risk === 'HIGH' ? '#e74c3c' : imp.risk === 'MEDIUM' ? '#f39c12' : '#2ecc71'}`,
        }}>
          <strong>{imp.symbol}</strong>
          <span style={{ color: '#999', marginLeft: 8 }}>({imp.symbol_kind})</span>
          <span style={{
            marginLeft: 8, fontSize: 11, padding: '1px 6px', borderRadius: 4,
            backgroundColor: imp.risk === 'CRITICAL' || imp.risk === 'HIGH' ? '#ffeef0' : '#fef9e7',
            color: imp.risk === 'CRITICAL' || imp.risk === 'HIGH' ? '#cb2431' : '#b7950b',
          }}>{imp.risk}</span>
          {imp.affected_symbols.length > 0 && (
            <p style={{ margin: '4px 0 0', color: '#666', fontSize: 12 }}>
              影响 {imp.affected_symbols.length} 个符号: {imp.affected_symbols.slice(0, 5).join(', ')}{imp.affected_symbols.length > 5 ? '...' : ''}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function FindingsList({ findings }: { findings: ReviewFinding[] }) {
  if (!findings.length) return null;
  const sevIcons: Record<string, string> = { CRITICAL: '\u{1F534}', HIGH: '\u{1F7E1}', MEDIUM: '\u{1F7E0}', LOW: '\u{1F7E2}', INFO: 'ℹ️' };
  return (
    <div style={{ marginTop: 12 }}>
      <h4 style={{ fontSize: 14, fontWeight: 600, marginBottom: 6, color: '#555' }}>逐文件分析</h4>
      {findings.map((f, idx) => (
        <div key={idx} style={{
          padding: '8px 12px', marginBottom: 6, borderRadius: 6,
          border: '1px solid #eee', fontSize: 13,
        }}>
          <span>{sevIcons[f.severity] || 'ℹ️'} <strong>[{f.severity}]</strong> {f.category}</span>
          <p style={{ margin: '4px 0 0', color: '#333' }}>{f.message}</p>
          {f.suggestion && <p style={{ margin: '2px 0 0', color: '#666', fontSize: 12 }}>{'💡'} {f.suggestion}</p>}
        </div>
      ))}
    </div>
  );
}

export default function FileChangeList({
  changes, fileAnalyses, commitHash, repoPath,
}: {
  changes: DiffChange[];
  fileAnalyses: FileAnalysis[];
  commitHash: string;
  repoPath: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [openFile, setOpenFile] = useState<string | null>(null);
  const [analyzingFiles, setAnalyzingFiles] = useState<Record<string, boolean>>({});
  const [localAnalyses, setLocalAnalyses] = useState<Record<string, FileAnalysis>>({});

  if (changes.length === 0) return null;

  const visible = expanded ? changes : changes.slice(0, DEFAULT_SHOW);
  const hasMore = changes.length > DEFAULT_SHOW;

  // Build a map of file → FileAnalysis from props + local state
  const getAnalysis = (file: string): FileAnalysis | undefined => {
    return localAnalyses[file] || fileAnalyses.find(fa => fa.file === file);
  };

  const handleAnalyze = async (file: string) => {
    setAnalyzingFiles(prev => ({ ...prev, [file]: true }));
    try {
      const result = await triggerFileAnalysis(commitHash, file, repoPath);
      const existing = getAnalysis(file);
      if (existing) {
        setLocalAnalyses(prev => ({
          ...prev,
          [file]: { ...existing, findings: result.findings, analysis_status: result.analysis_status },
        }));
      }
    } catch (e: any) {
      alert('分析失败: ' + (e.message || '未知错误'));
    } finally {
      setAnalyzingFiles(prev => ({ ...prev, [file]: false }));
    }
  };

  const handleToggle = (file: string) => {
    setOpenFile(openFile === file ? null : file);
  };

  return (
    <div style={{ marginTop: 32 }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
        Changed Files ({changes.length})
      </h3>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>File</th>
            <th style={{ ...thStyle, width: 60 }}>Added</th>
            <th style={{ ...thStyle, width: 60 }}>Removed</th>
            <th style={{ ...thStyle, width: 100 }}>Analysis</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((c, idx) => {
            const analysis = getAnalysis(c.file);
            const isOpen = openFile === c.file;
            const isAnalyzing = analyzingFiles[c.file];
            const hasResults = analysis && analysis.analysis_status === 'completed';
            return (
              <tr key={idx}>
                <td colSpan={4} style={{ padding: 0 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <tbody>
                      <tr
                        onClick={() => handleToggle(c.file)}
                        style={{ cursor: 'pointer', backgroundColor: isOpen ? '#ebf5fb' : undefined }}
                      >
                        <td style={tdStyle}>
                          <code style={{ color: isOpen ? '#3498db' : undefined }}>{c.file}</code>
                          {analysis?.module && <ModuleTag module={analysis.module} />}
                        </td>
                        <td style={{ ...tdStyle, width: 60, color: '#27ae60' }}>+{c.added}</td>
                        <td style={{ ...tdStyle, width: 60, color: '#e74c3c' }}>-{c.removed}</td>
                        <td style={{ ...tdStyle, width: 100 }}>
                          {isAnalyzing ? (
                            <span style={{ fontSize: 12, color: '#95a5a6' }}>分析中...</span>
                          ) : hasResults ? (
                            <span style={{ fontSize: 12, color: '#27ae60' }}>已完成</span>
                          ) : (
                            <span style={{ fontSize: 12, color: '#bdc3c7' }}>未分析</span>
                          )}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={4} style={{ padding: '0 12px 12px' }}>
                            {analysis?.diff_text && (
                              <>
                                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                                  <button
                                    onClick={(e) => { e.stopPropagation(); handleAnalyze(c.file); }}
                                    disabled={isAnalyzing}
                                    style={{
                                      padding: '6px 16px', borderRadius: 6, border: 'none',
                                      fontSize: 13, fontWeight: 600, cursor: isAnalyzing ? 'wait' : 'pointer',
                                      backgroundColor: isAnalyzing ? '#ccc' : '#f39c12',
                                      color: '#fff',
                                    }}
                                  >
                                    {isAnalyzing ? '分析中...' : hasResults ? '重新分析' : '分析这段改动'}
                                  </button>
                                </div>
                                <DiffPreview diffText={analysis.diff_text} />
                                <ImpactSummary impacts={analysis.impacts} />
                                {hasResults && <FindingsList findings={analysis.findings} />}
                              </>
                            )}
                            {!analysis?.diff_text && (
                              <p style={{ color: '#95a5a6', fontSize: 13 }}>无差异数据</p>
                            )}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            marginTop: 8, padding: '6px 16px', border: '1px solid #ddd',
            borderRadius: 4, background: '#fff', cursor: 'pointer', fontSize: 13, color: '#3498db',
          }}
        >
          {expanded ? `Show fewer` : `Show all ${changes.length} files`}
        </button>
      )}
    </div>
  );
}
