import { useEffect, useRef, useState } from 'react';
import { Network, type Edge } from 'vis-network';
import { DataSet } from 'vis-data';
import type { ImpactItem } from '../types';

interface CommunityGraphProps {
  impacts: ImpactItem[];
}

const GROUP_COLORS = [
  '#3498db', '#e74c3c', '#2ecc71', '#f39c12',
  '#9b59b6', '#1abc9c', '#e67e22', '#34495e',
];

export default function CommunityGraph({ impacts }: CommunityGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const [showTooltip, setShowTooltip] = useState(false);

  useEffect(() => {
    if (!containerRef.current || impacts.length === 0) return;

    // 如果已经初始化过，不重新创建
    if (networkRef.current) return;

    const nodes: Array<{ id: string; label: string; color: string; group: string }> = [];
    const edges: Edge[] = [];

    impacts.forEach((item, idx) => {
      const color = GROUP_COLORS[idx % GROUP_COLORS.length];
      nodes.push({
        id: `sym-${item.symbol}`,
        label: `${item.symbol}\n[${item.risk}]`,
        color,
        group: `g-${idx}`,
      });

      item.affected_processes.slice(0, 8).forEach((proc, pi) => {
        const procId = `proc-${idx}-${pi}`;
        const shortLabel = proc.length > 35 ? proc.substring(0, 32) + '...' : proc;
        nodes.push({
          id: procId,
          label: shortLabel,
          color: '#ecf0f1',
          group: `g-${idx}`,
        });
        edges.push({ from: `sym-${item.symbol}`, to: procId });
      });
    });

    const network = new Network(
      containerRef.current,
      { nodes: new DataSet(nodes), edges: new DataSet<Edge>(edges) },
      {
        layout: { improvedLayout: true },
        physics: { stabilization: { iterations: 100 } },
        edges: { smooth: false },
        groups: impacts.reduce<Record<string, { shape: string; color: string }>>((acc, _, i) => {
          acc[`g-${i}`] = { shape: 'box', color: GROUP_COLORS[i % GROUP_COLORS.length] };
          return acc;
        }, {}),
        interaction: { hover: true, zoomView: true },
      },
    );

    // 布局稳定后关闭物理引擎，这样拖拽单个节点不会影响其他节点
    network.once('stabilizationIterationsDone', () => {
      network.setOptions({ physics: { enabled: false } });
    });

    networkRef.current = network;

    return () => {
      networkRef.current?.destroy();
      networkRef.current = null;
    };
  }, [impacts]);

  if (impacts.length === 0) return null;

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>关联分析</h2>
        <span
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
          style={{
            cursor: 'help', fontSize: 14, color: '#999',
            border: '1px solid #ddd', borderRadius: '50%',
            width: 20, height: 20, display: 'inline-flex',
            alignItems: 'center', justifyContent: 'center',
            position: 'relative',
          }}
        >?
          {showTooltip && (
            <span style={{
              position: 'absolute', left: '100%', top: '50%', transform: 'translateY(-50%)',
              marginLeft: 8, padding: '8px 12px', borderRadius: 6,
              background: '#333', color: '#fff', fontSize: 12, whiteSpace: 'nowrap',
              zIndex: 100, pointerEvents: 'none',
            }}>
              展示被修改的方法及其影响的执行流程。每种颜色代表一个被修改的方法，叶子节点是受影响的处理流程。
            </span>
          )}
        </span>
      </div>
      <p style={{ fontSize: 13, color: '#7f8c8d', marginBottom: 8 }}>
        每种颜色代表一个被修改的方法，叶子节点是受影响的执行流程。
      </p>
      <div
        ref={containerRef}
        style={{
          height: 350,
          border: '1px solid #ddd',
          borderRadius: 8,
          backgroundColor: '#fafafa',
        }}
      />
    </div>
  );
}
