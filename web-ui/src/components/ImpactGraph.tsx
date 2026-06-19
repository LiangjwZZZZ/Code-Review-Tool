import { useEffect, useRef } from 'react';
import { Network, type Edge } from 'vis-network';
import { DataSet } from 'vis-data';
import type { ImpactItem } from '../types';

interface ImpactGraphProps {
  impacts: ImpactItem[];
  fileModules?: Record<string, string>;
}

const MODULE_COLORS = [
  '#3498db', '#e74c3c', '#2ecc71', '#f39c12',
  '#9b59b6', '#1abc9c', '#e67e22', '#34495e',
  '#16a085', '#c0392b', '#2980b9', '#8e44ad',
];

function getModuleColor(module: string, usedColors: Record<string, string>): string {
  if (usedColors[module]) return usedColors[module];
  const idx = Object.keys(usedColors).length % MODULE_COLORS.length;
  usedColors[module] = MODULE_COLORS[idx];
  return usedColors[module];
}

function buildGraph(impacts: ImpactItem[], fileModules?: Record<string, string>) {
  const nodes: Array<{ id: string; label: string; color: string; title: string; shape: string }> = [];
  const edges: Array<{ from: string; to: string; color?: string; dashes?: boolean; width?: number }> = [];
  const moduleColors: Record<string, string> = {};

  for (const item of impacts) {
    // Determine color: by module if available, else by risk
    let color: string;
    let module: string | undefined;
    if (fileModules) {
      module = fileModules[item.file];
      if (module) {
        color = getModuleColor(module, moduleColors);
      } else {
        color = '#95a5a6'; // unknown module
      }
    } else {
      color = '#e74c3c'; // fallback: all changed nodes red
    }

    nodes.push({
      id: item.symbol,
      label: `${item.symbol}\n[${item.risk}]`,
      color: color,
      title: `${item.symbol}\n${item.file}${module ? `\nModule: ${module}` : ''}\nRisk: ${item.risk}\nKind: ${item.symbol_kind}\nDirection: ${item.direction}`,
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

  return { nodes, edges, usedModules: Object.keys(moduleColors) };
}

export default function ImpactGraph({ impacts, fileModules }: ImpactGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);

  useEffect(() => {
    if (!containerRef.current || impacts.length === 0) return;

    if (networkRef.current) {
      networkRef.current.destroy();
    }

    const { nodes, edges, usedModules } = buildGraph(impacts, fileModules);

    networkRef.current = new Network(
      containerRef.current,
      { nodes: new DataSet(nodes), edges: new DataSet<Edge>(edges) },
      {
        layout: { improvedLayout: true },
        physics: { stabilization: { iterations: 100 } },
        edges: { smooth: true },
        interaction: { hover: true, tooltipDelay: 200, zoomView: false },
      },
    );

    return () => {
      networkRef.current?.destroy();
      networkRef.current = null;
    };
  }, [impacts, fileModules]);

  if (impacts.length === 0) return null;

  // Build module color legend
  const moduleColors: Record<string, string> = {};
  if (fileModules) {
    impacts.forEach(item => {
      const m = fileModules[item.file];
      if (m) getModuleColor(m, moduleColors);
    });
  }

  return (
    <div style={{ marginTop: 32 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <h2 style={{ margin: 0 }}>影响图</h2>
        <span
          title="展示方法之间的调用关系。方形节点是被修改的方法，椭圆节点是调用它的代码。连线表示「谁调用了谁」。颜色按模块区分。"
          style={{
            cursor: 'help', fontSize: 14, color: '#999',
            border: '1px solid #ddd', borderRadius: '50%',
            width: 20, height: 20, display: 'inline-flex',
            alignItems: 'center', justifyContent: 'center',
          }}
        >?</span>
      </div>
      <div style={{ marginBottom: 8, display: 'flex', gap: 16, fontSize: 13, flexWrap: 'wrap' }}>
        {Object.keys(moduleColors).length > 0 && (
          <>
            {Object.entries(moduleColors).map(([m, c]) => (
              <span key={m}><span style={{ color: c }}>■</span> {m}</span>
            ))}
            <span style={{ color: '#999' }}>|</span>
          </>
        )}
        <span><span style={{ color: '#e74c3c' }}>■</span> 被修改的方法</span>
        <span><span style={{ color: '#85c1e9' }}>●</span> 调用方</span>
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
