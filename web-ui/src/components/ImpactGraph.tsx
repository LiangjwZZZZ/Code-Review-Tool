import { useEffect, useRef } from 'react';
import { Network, type Edge } from 'vis-network';
import { DataSet } from 'vis-data';
import type { ImpactItem } from '../types';

interface ImpactGraphProps {
  impacts: ImpactItem[];
}

const RISK_COLORS: Record<string, string> = {
  CRITICAL: '#e74c3c',
  HIGH: '#e67e22',
  MEDIUM: '#f1c40f',
  LOW: '#2ecc71',
};

function buildGraph(impacts: ImpactItem[]) {
  const nodes: Array<{ id: string; label: string; color: string; title: string; shape: string }> = [];
  const edges: Array<{ from: string; to: string; color?: string; dashes?: boolean }> = [];

  for (const item of impacts) {
    const color = RISK_COLORS[item.risk] || '#95a5a6';
    nodes.push({
      id: item.symbol,
      label: `${item.symbol}\n[${item.risk}]`,
      color: color,
      title: `${item.symbol}\n${item.file}\nRisk: ${item.risk}\nKind: ${item.symbol_kind}`,
      shape: 'box',
    });

    for (const aff of item.affected_symbols.slice(0, 15)) {
      const affId = `aff-${aff}`;
      if (!nodes.find(n => n.id === affId)) {
        nodes.push({
          id: affId,
          label: aff,
          color: '#85c1e9',
          title: `Affected: ${aff}`,
          shape: 'ellipse',
        });
      }
      edges.push({ from: item.symbol, to: affId, color: '#7f8c8d' });
    }
  }

  return { nodes, edges };
}

export default function ImpactGraph({ impacts }: ImpactGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);

  useEffect(() => {
    if (!containerRef.current || impacts.length === 0) return;

    if (networkRef.current) {
      networkRef.current.destroy();
    }

    const { nodes, edges } = buildGraph(impacts);

    networkRef.current = new Network(
      containerRef.current,
      { nodes: new DataSet(nodes), edges: new DataSet<Edge>(edges) },
      {
        layout: { improvedLayout: true },
        physics: { stabilization: { iterations: 100 } },
        edges: { smooth: true },
        interaction: { hover: true, tooltipDelay: 200 },
      },
    );

    return () => {
      networkRef.current?.destroy();
      networkRef.current = null;
    };
  }, [impacts]);

  if (impacts.length === 0) return null;

  return (
    <div style={{ marginTop: 32 }}>
      <h2 style={{ marginBottom: 8 }}>Impact Graph</h2>
      <div style={{ marginBottom: 8, display: 'flex', gap: 16, fontSize: 13 }}>
        <span><span style={{ color: '#e74c3c' }}>■</span> CRITICAL</span>
        <span><span style={{ color: '#e67e22' }}>■</span> HIGH</span>
        <span><span style={{ color: '#f1c40f' }}>■</span> MEDIUM</span>
        <span><span style={{ color: '#2ecc71' }}>■</span> LOW</span>
        <span><span style={{ color: '#85c1e9' }}>●</span> Affected</span>
      </div>
      <div
        ref={containerRef}
        style={{
          height: 400,
          border: '1px solid #ddd',
          borderRadius: 8,
          backgroundColor: '#fafafa',
        }}
      />
    </div>
  );
}
