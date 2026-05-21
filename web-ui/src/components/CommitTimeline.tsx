import type { CommitNode, BranchInfo } from '../api';

interface CommitTimelineProps {
  commits: CommitNode[];
  branches: BranchInfo[];
  selectedBranch: string;
  onViewReport: (hash: string) => void;
  onAnalyze: (hash: string) => void;
  analyzing: Set<string>;
}

const BRANCH_COLORS = [
  '#3498db', '#e74c3c', '#2ecc71', '#f39c12',
  '#9b59b6', '#1abc9c', '#e67e22', '#34495e',
];

function getBranchColor(branches: BranchInfo[], branchName: string): string {
  const idx = branches.findIndex(b => b.name === branchName);
  return idx >= 0 ? BRANCH_COLORS[idx % BRANCH_COLORS.length] : '#95a5a6';
}

export default function CommitTimeline({
  commits, branches, selectedBranch,
  onViewReport, onAnalyze, analyzing,
}: CommitTimelineProps) {
  const dotColor = selectedBranch ? getBranchColor(branches, selectedBranch) : '#3498db';

  return (
    <div>
      {/* Timeline */}
      <div style={{ position: 'relative', paddingLeft: 30 }}>
        {/* Vertical line */}
        <div
          style={{
            position: 'absolute',
            left: 21,
            top: 12,
            bottom: 12,
            width: 2,
            backgroundColor: dotColor,
            zIndex: 0,
          }}
        />

        {commits.map((c, idx) => {
          const isAnalyzed = c.analyzed;
          const isAnalyzing = analyzing.has(c.hash);
          const isLast = idx === commits.length - 1;

          return (
            <div key={c.hash} style={{ position: 'relative', zIndex: 1 }}>
              <div style={{ display: 'flex', gap: 12, padding: '6px 0' }}>
                {/* Dot */}
                <div style={{
                  width: 16,
                  height: 16,
                  borderRadius: '50%',
                  backgroundColor: isAnalyzed ? '#27ae60' : isAnalyzing ? '#f39c12' : '#bdc3c7',
                  border: '3px solid #fff',
                  boxShadow: `0 0 0 2px ${isAnalyzed ? '#27ae60' : isAnalyzing ? '#f39c12' : '#bdc3c7'}`,
                  flexShrink: 0,
                  marginTop: 6,
                  cursor: isAnalyzing ? 'wait' : 'pointer',
                }} />

                {/* Card */}
                <div
                  onClick={() => {
                    if (isAnalyzing) return;
                    onViewReport(c.hash);
                  }}
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: 8,
                    border: '1px solid ' + (isAnalyzed ? '#a9dfbf' : '#e8e8e8'),
                    backgroundColor: isAnalyzed ? '#f0faf3' : isAnalyzing ? '#fef9e7' : '#fff',
                    cursor: isAnalyzing ? 'wait' : 'pointer',
                    marginBottom: 8,
                  }}
                >
                  <div style={{ fontSize: 11, color: '#95a5a6', marginBottom: 2 }}>
                    <code>{c.hash.slice(0, 12)}</code>
                    {c.time && (
                      <>
                        <span style={{ margin: '0 6px' }}>&middot;</span>
                        {new Date(c.time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}
                      </>
                    )}
                    <span style={{ margin: '0 6px' }}>&middot;</span>
                    {c.author}
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 500, color: '#2c3e50' }}>
                    {c.message || '(no message)'}
                  </div>

                  {/* Branch labels */}
                  {branches.filter(b => b.hash === c.hash && !b.name.startsWith('HEAD') && !b.name.startsWith('remotes/')).map(b => (
                    <span key={b.name} style={{
                      display: 'inline-block',
                      marginTop: 4,
                      marginRight: 6,
                      padding: '1px 8px',
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 600,
                      color: '#fff',
                      backgroundColor: getBranchColor(branches, b.name),
                    }}>{b.name}</span>
                  ))}

                  {branches.filter(b => b.hash === c.hash && b.name.startsWith('remotes/')).map(b => (
                    <span key={b.name} style={{
                      display: 'inline-block',
                      marginTop: 4,
                      marginRight: 6,
                      padding: '1px 8px',
                      borderRadius: 4,
                      fontSize: 11,
                      fontWeight: 600,
                      color: '#7f8c8d',
                      backgroundColor: '#f0f0f0',
                    }}>{b.name}</span>
                  ))}

                  <div style={{ fontSize: 12, marginTop: 4 }}>
                    {isAnalyzing ? (
                      <span style={{ color: '#e67e22' }}>⏳ Analyzing...</span>
                    ) : isAnalyzed ? (
                      <span style={{ color: '#27ae60' }}>✓ Click to view</span>
                    ) : (
                      <span style={{ color: '#95a5a6' }}>Click to preview & analyze</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
