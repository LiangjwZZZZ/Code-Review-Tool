import { useState } from 'react';
import type { DiffChange } from '../types';

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

export default function FileChangeList({ changes, selectedFile, onSelectFile }: {
  changes: DiffChange[];
  selectedFile: string | null;
  onSelectFile: (file: string | null) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  if (changes.length === 0) return null;

  const visible = expanded ? changes : changes.slice(0, DEFAULT_SHOW);
  const hasMore = changes.length > DEFAULT_SHOW;

  return (
    <div style={{ marginTop: 32 }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>
        Changed Files ({changes.length})
      </h3>
      <table style={tableStyle}>
        <thead>
          <tr>
            <th style={thStyle}>File</th>
            <th style={{ ...thStyle, width: 80 }}>Added</th>
            <th style={{ ...thStyle, width: 80 }}>Removed</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((c, idx) => (
            <tr key={idx}
              onClick={() => onSelectFile(selectedFile === c.file ? null : c.file)}
              style={{ cursor: 'pointer', backgroundColor: selectedFile === c.file ? '#ebf5fb' : undefined }}
            >
              <td style={tdStyle}>
                <code style={{ color: selectedFile === c.file ? '#3498db' : undefined }}>{c.file}</code>
              </td>
              <td style={{ ...tdStyle, color: '#27ae60' }}>+{c.added}</td>
              <td style={{ ...tdStyle, color: '#e74c3c' }}>-{c.removed}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            marginTop: 8,
            padding: '6px 16px',
            border: '1px solid #ddd',
            borderRadius: 4,
            background: '#fff',
            cursor: 'pointer',
            fontSize: 13,
            color: '#3498db',
          }}
        >
          {expanded ? `Show fewer` : `Show all ${changes.length} files`}
        </button>
      )}
    </div>
  );
}
