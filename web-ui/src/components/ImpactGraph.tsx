import { useEffect, useRef, useState } from 'react';
import { Network, type Edge } from 'vis-network';
import { DataSet } from 'vis-data';
import type { ImpactItem, ReviewFinding } from '../types';

interface ImpactGraphProps {
  impacts: ImpactItem[];
  fileModules?: Record<string, string>;
  findings?: ReviewFinding[];
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
          shape: 'box',
        });
      }
      edges.push({ from: item.symbol, to: affId, color: '#7f8c8d' });
    }
  }

  return { nodes, edges, usedModules: Object.keys(moduleColors) };
}

export default function ImpactGraph({ impacts, fileModules, findings = [] }: ImpactGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const networkRef = useRef<Network | null>(null);
  const [showTooltip, setShowTooltip] = useState(false);
  const [hoveredImpact, setHoveredImpact] = useState<ImpactItem | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [isTooltipHovered, setIsTooltipHovered] = useState(false);
  const hideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);
  const dragStartYRef = useRef(0);
  const scrollTopRef = useRef(0);

  useEffect(() => {
    if (!containerRef.current || impacts.length === 0) return;

    // 如果已经初始化过，不重新创建
    if (networkRef.current) return;

    const { nodes, edges, usedModules } = buildGraph(impacts, fileModules);

    const nodesDataSet = new DataSet(nodes) as any;
    const edgesDataSet = new DataSet<Edge>(edges);

    const network = new Network(
      containerRef.current,
      { nodes: nodesDataSet, edges: edgesDataSet },
      {
        layout: { improvedLayout: true },
        physics: {
          stabilization: { iterations: 200 },
          repulsion: { nodeDistance: 150, centralGravity: 0.1 },
        },
        edges: { smooth: false },
        interaction: { hover: true, tooltipDelay: 200, zoomView: true },
      },
    );

    // 布局稳定后关闭物理引擎
    network.once('stabilizationIterationsDone', () => {
      network.setOptions({ physics: { enabled: false } });
    });

    // 监听鼠标悬停事件
    network.on('hoverNode', (params) => {
      // 清除隐藏定时器
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current);
        hideTimeoutRef.current = null;
      }

      const nodeId = params.node;
      // 查找对应的 ImpactItem
      const impact = impacts.find(imp => imp.symbol === nodeId);
      if (impact) {
        setHoveredImpact(impact);
        // 获取鼠标位置
        setTooltipPos({ x: params.event?.clientX || 0, y: params.event?.clientY || 0 });
      }
    });

    network.on('blurNode', () => {
      // 延迟隐藏，给鼠标移到 tooltip 的时间
      hideTimeoutRef.current = setTimeout(() => {
        if (!isTooltipHovered) {
          setHoveredImpact(null);
        }
      }, 200);
    });


    networkRef.current = network;

    return () => {
      networkRef.current?.destroy();
      networkRef.current = null;
    };
  }, [impacts, fileModules, findings]);

  // 提示显示时禁用页面滚轮
  useEffect(() => {
    if (!hoveredImpact) return;

    const preventScroll = (e: WheelEvent) => {
      e.preventDefault();
    };

    // 禁用页面滚轮
    document.addEventListener('wheel', preventScroll, { passive: false });

    return () => {
      document.removeEventListener('wheel', preventScroll);
    };
  }, [hoveredImpact]);

  // 提示内容拖拽滚动
  const handleTooltipMouseDown = (e: React.MouseEvent) => {
    if (!tooltipRef.current) return;
    e.preventDefault(); // 防止选中文本
    isDraggingRef.current = true;
    dragStartYRef.current = e.clientY;
    scrollTopRef.current = tooltipRef.current.scrollTop;

    // 添加全局事件监听
    const handleMouseMove = (me: MouseEvent) => {
      if (!isDraggingRef.current || !tooltipRef.current) return;
      const deltaY = dragStartYRef.current - me.clientY;
      tooltipRef.current.scrollTop = scrollTopRef.current + deltaY;
    };

    const handleMouseUp = () => {
      isDraggingRef.current = false;
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

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
              展示方法之间的调用关系。节点是被修改的方法或调用它的代码，连线表示「谁调用了谁」。颜色按模块区分。
            </span>
          )}
        </span>
      </div>
      <div style={{ marginBottom: 8, display: 'flex', gap: 16, fontSize: 13, flexWrap: 'wrap', alignItems: 'center' }}>
        {Object.keys(moduleColors).length > 0 ? (
          <>
            {Object.entries(moduleColors).map(([m, c]) => (
              <span key={m}><span style={{ color: c }}>■</span> {m}</span>
            ))}
            <span style={{ color: '#999' }}>|</span>
          </>
        ) : (
          <span><span style={{ color: '#e74c3c' }}>■</span> 被修改的方法</span>
        )}
        <span><span style={{ color: '#85c1e9' }}>●</span> 调用方</span>
      </div>
      <div
        ref={containerRef}
        style={{
          height: 400,
          border: '1px solid #ddd',
          borderRadius: 8,
          backgroundColor: '#fafafa',
          position: 'relative',
        }}
      />
      {/* 自定义悬停提示 */}
      {hoveredImpact && (
        <div
          ref={tooltipRef}
          onMouseEnter={() => {
            setIsTooltipHovered(true);
            if (hideTimeoutRef.current) {
              clearTimeout(hideTimeoutRef.current);
              hideTimeoutRef.current = null;
            }
          }}
          onMouseLeave={() => {
            setIsTooltipHovered(false);
            setHoveredImpact(null);
            isDraggingRef.current = false;
          }}
          onMouseDown={handleTooltipMouseDown}
          style={{
            position: 'fixed',
            left: tooltipPos.x + 16,
            top: tooltipPos.y - 10,
            maxWidth: 400,
            maxHeight: 300,
            padding: '12px 16px',
            borderRadius: 8,
            background: '#fff',
            border: '1px solid #ddd',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            fontSize: 13,
            zIndex: 1000,
            overflowY: 'auto',
            cursor: 'grab',
            userSelect: 'none',
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: 8, color: '#2c3e50' }}>
            {hoveredImpact.symbol}
            <span style={{
              marginLeft: 8,
              fontSize: 11,
              padding: '2px 6px',
              borderRadius: 4,
              backgroundColor: hoveredImpact.risk === 'CRITICAL' ? '#ffeef0' : hoveredImpact.risk === 'HIGH' ? '#fff3e0' : '#e8f5e9',
              color: hoveredImpact.risk === 'CRITICAL' ? '#e74c3c' : hoveredImpact.risk === 'HIGH' ? '#f39c12' : '#27ae60',
            }}>{hoveredImpact.risk}</span>
          </div>
          <div style={{ color: '#666', marginBottom: 8 }}>
            📁 {hoveredImpact.file}
          </div>

          {/* 调用方列表 */}
          {hoveredImpact.affected_symbols.length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontWeight: 500, marginBottom: 4, color: '#555' }}>📞 调用方 ({hoveredImpact.affected_symbols.length})</div>
              <div style={{ maxHeight: 120, overflowY: 'auto' }}>
                {hoveredImpact.affected_symbols.slice(0, 8).map((aff, i) => (
                  <div key={i} style={{ color: '#666', fontSize: 12, padding: '2px 0' }}>
                    • {aff}
                  </div>
                ))}
                {hoveredImpact.affected_symbols.length > 8 && (
                  <div style={{ color: '#999', fontSize: 12 }}>
                    ... 还有 {hoveredImpact.affected_symbols.length - 8} 个
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 相关审查意见 */}
          {findings.length > 0 && (
            <div>
              <div style={{ fontWeight: 500, marginBottom: 4, color: '#555' }}>🔍 审查意见</div>
              <div style={{ maxHeight: 100, overflowY: 'auto' }}>
                {findings.slice(0, 3).map((f, i) => (
                  <div key={i} style={{ fontSize: 12, padding: '2px 0', color: f.severity === 'CRITICAL' ? '#e74c3c' : f.severity === 'HIGH' ? '#f39c12' : '#666' }}>
                    [{f.severity}] {f.message}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
