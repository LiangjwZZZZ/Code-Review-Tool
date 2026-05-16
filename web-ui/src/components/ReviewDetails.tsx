import type { ReviewFinding } from '../types';

interface ReviewDetailsProps {
  findings: ReviewFinding[];
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: '#e74c3c',
  HIGH: '#e67e22',
  MEDIUM: '#f1c40f',
  LOW: '#2ecc71',
};

export default function ReviewDetails({ findings }: ReviewDetailsProps) {
  if (findings.length === 0) return null;

  return (
    <div style={{ marginTop: 32 }}>
      <h2 style={{ marginBottom: 12 }}>Review Findings</h2>
      {findings.map((f, i) => (
        <div
          key={i}
          style={{
            padding: 16,
            marginBottom: 12,
            borderLeft: `4px solid ${SEVERITY_COLORS[f.severity] || '#95a5a6'}`,
            backgroundColor: '#f8f9fa',
            borderRadius: 4,
          }}
        >
          <div style={{ display: 'flex', gap: 8, marginBottom: 4, alignItems: 'center' }}>
            <span
              style={{
                backgroundColor: SEVERITY_COLORS[f.severity] || '#95a5a6',
                color: '#fff',
                padding: '2px 8px',
                borderRadius: 4,
                fontSize: 12,
                fontWeight: 600,
              }}
            >
              {f.severity}
            </span>
            <span style={{ fontSize: 12, color: '#7f8c8d' }}>{f.category}</span>
          </div>
          <p style={{ margin: '4px 0', color: '#2c3e50' }}>{f.message}</p>
          {f.suggestion && (
            <p style={{ margin: '4px 0', fontSize: 13, color: '#555' }}>
              <strong>Suggestion:</strong> {f.suggestion}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
