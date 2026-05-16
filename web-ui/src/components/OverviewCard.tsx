import type { Report } from '../types';

const cardStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 12,
  padding: 24,
  marginBottom: 24,
  background: '#fafafa',
};

const riskColors: Record<string, string> = {
  CRITICAL: '#e74c3c',
  HIGH: '#e67e22',
  MEDIUM: '#f1c40f',
  LOW: '#2ecc71',
};

export default function OverviewCard({ report }: { report: Report }) {
  const totalChanges = report.changes.reduce((a, c) => a + c.added + c.removed, 0);

  return (
    <div style={cardStyle}>
      <h2 style={{ margin: 0, fontSize: 16, color: '#666' }}>Review Report</h2>
      <h1 style={{ margin: '4px 0', fontSize: 20 }}>
        {report.commit_hash.slice(0, 12)} — {report.commit_message}
      </h1>
      <p style={{ color: '#888', fontSize: 14 }}>
        {report.author} | {report.changes.length} files | {totalChanges} changes
      </p>
      <div style={{ marginTop: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        <span style={{
          padding: '4px 12px', borderRadius: 6, fontWeight: 700, fontSize: 14,
          background: riskColors[report.risk_level] || '#999', color: '#fff',
        }}>
          {report.risk_level}
        </span>
        <span style={{ color: '#555', fontSize: 14 }}>{report.summary}</span>
      </div>
    </div>
  );
}
