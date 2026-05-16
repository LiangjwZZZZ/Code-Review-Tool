import { useEffect, useState } from 'react';
import { fetchReportsList } from '../api';
import type { ReportSummary } from '../api';

const RISK_COLORS: Record<string, string> = {
  CRITICAL: '#e74c3c',
  HIGH: '#e67e22',
  MEDIUM: '#f1c40f',
  LOW: '#2ecc71',
};

const containerStyle: React.CSSProperties = {
  maxWidth: 800,
  margin: '0 auto',
  padding: 24,
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
};

export default function ReportListPage() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchReportsList()
      .then(setReports)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const repoName = reports.length > 0 ? reports[0].repo_name : '';

  return (
    <div style={containerStyle}>
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>
        {repoName ? `${repoName} - Review Reports` : 'Review Reports'}
      </h1>
      <p style={{ fontSize: 13, color: '#7f8c8d', marginBottom: 20 }}>
        {reports.length} report(s) found
      </p>

      {loading && <p>Loading...</p>}

      {!loading && reports.length === 0 && (
        <p style={{ color: '#95a5a6' }}>
          No reports yet. Run <code>review check &lt;commit&gt;</code> to create one.
        </p>
      )}

      {reports.map((r) => (
        <a
          key={r.commit}
          href={`/report/${r.commit}`}
          style={{
            display: 'block',
            textDecoration: 'none',
            color: 'inherit',
            padding: 16,
            marginBottom: 12,
            border: '1px solid #e0e0e0',
            borderRadius: 8,
            backgroundColor: '#fff',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12, color: '#95a5a6', marginBottom: 4 }}>
                <code>{r.commit.slice(0, 12)}</code>
                <span style={{ margin: '0 8px' }}>&middot;</span>
                {r.commit_time ? new Date(r.commit_time).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                <span style={{ margin: '0 8px' }}>&middot;</span>
                {r.author}
              </div>
              <div style={{ fontSize: 15, fontWeight: 600, color: '#2c3e50', marginBottom: 4 }}>
                {r.commit_message || '(no message)'}
              </div>
              {r.commit_body && (
                <div
                  style={{
                    fontSize: 13,
                    color: '#7f8c8d',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.5,
                    display: '-webkit-box',
                    WebkitLineClamp: 3,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  {r.commit_body}
                </div>
              )}
            </div>
            <span
              style={{
                marginLeft: 12,
                padding: '2px 10px',
                borderRadius: 4,
                fontSize: 12,
                fontWeight: 600,
                color: '#fff',
                backgroundColor: RISK_COLORS[r.risk_level] || '#95a5a6',
                whiteSpace: 'nowrap',
              }}
            >
              {r.risk_level}
            </span>
          </div>
          <div style={{ fontSize: 12, color: '#95a5a6', marginTop: 8 }}>
            {r.changes_count} file(s)
          </div>
        </a>
      ))}
    </div>
  );
}
