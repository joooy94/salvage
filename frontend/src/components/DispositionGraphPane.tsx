import { Network } from "lucide-react";
import { useMemo, useState } from "react";
import { DispositionGraph, DispositionGraphNode, WikiPage } from "../api";

type DispositionGraphPaneProps = {
  graph?: DispositionGraph | null;
  onOpenWiki: (pageOrPath: WikiPage | string) => void;
};

const nodeTypeLabels: Record<string, string> = {
  accident: "事故",
  feature: "特征",
  risk: "风险",
  procedure: "工艺",
  tool: "工具",
  standard: "标准",
  case: "案例",
  synthesis: "综合",
  evidence: "依据",
  decision: "决策",
};

function DispositionGraphPane({ graph, onOpenWiki }: DispositionGraphPaneProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const nodes = graph?.nodes ?? [];
  const edges = graph?.edges ?? [];
  const nodeMap = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const graphLayout = useMemo(() => layoutDispositionGraph(nodes), [nodes]);
  const positions = graphLayout.positions;
  const selectedEdges = selectedId ? edges.filter((edge) => edge.source === selectedId || edge.target === selectedId) : edges;
  const selectedNode = selectedId ? nodeMap.get(selectedId) : null;
  const relatedIds = useMemo(() => {
    if (!selectedId) return new Set<string>();
    const ids = new Set<string>([selectedId]);
    selectedEdges.forEach((edge) => {
      ids.add(edge.source);
      ids.add(edge.target);
    });
    return ids;
  }, [selectedEdges, selectedId]);

  if (!nodes.length) {
    return (
      <article className="agent-card">
        <div className="agent-card-body">
          暂无处置知识图谱。生成处置方案后，这里会显示“事故特征 → 风险 → 工艺 → 工具 → 依据”的推理链路。
        </div>
      </article>
    );
  }

  return (
    <div className="disposition-graph-pane">
      <div className="disposition-graph-header">
        <div>
          <div className="disposition-graph-title">
            <Network size={15} aria-hidden="true" />
            处置知识图谱
          </div>
          <div className="disposition-graph-subtitle">{nodes.length} 个实体 · {edges.length} 条处置关系</div>
        </div>
        <div className="disposition-graph-legend">
          {["feature", "risk", "procedure", "tool", "standard", "case"].map((type) => (
            <span key={type}><i className={`type-${type}`} />{nodeTypeLabels[type]}</span>
          ))}
        </div>
      </div>

      <div className="disposition-graph-canvas">
        <svg role="img" aria-label="处置知识图谱" style={{ height: graphLayout.height, minWidth: graphLayout.width }} viewBox={`0 0 ${graphLayout.width} ${graphLayout.height}`}>
          <defs>
            <marker id="disposition-arrow" markerHeight="7" markerWidth="7" orient="auto" refX="7" refY="3.5">
              <path d="M0,0 L7,3.5 L0,7 Z" />
            </marker>
          </defs>
          {edges.map((edge, index) => {
            const source = positions.get(edge.source);
            const target = positions.get(edge.target);
            if (!source || !target) return null;
            const active = !selectedId || edge.source === selectedId || edge.target === selectedId;
            const midX = (source.x + target.x) / 2;
            const midY = (source.y + target.y) / 2;
            return (
              <g key={`${edge.source}-${edge.target}-${index}`}>
                <line className={`disposition-edge ${active ? "active" : "muted"}`} markerEnd="url(#disposition-arrow)" x1={source.x} x2={target.x} y1={source.y} y2={target.y} />
                {selectedId && active ? <text className="disposition-edge-label" x={midX} y={midY - 4}>{edge.label}</text> : null}
              </g>
            );
          })}
          {nodes.map((node) => {
            const point = positions.get(node.id);
            if (!point) return null;
            const selected = selectedId === node.id;
            const related = !selectedId || relatedIds.has(node.id);
            return (
              <g
                className={`disposition-node type-${node.type} ${selected ? "selected" : ""} ${related ? "" : "muted"}`}
                key={node.id}
                onClick={() => setSelectedId(selected ? null : node.id)}
                onDoubleClick={() => node.source_page && onOpenWiki(node.source_page)}
                role="button"
                tabIndex={0}
                transform={`translate(${point.x} ${point.y})`}
              >
                <title>{node.summary || node.label}</title>
                <rect height="38" rx="7" width={nodeWidth(node)} x={-nodeWidth(node) / 2} y="-19" />
                <text dy="4">{shortLabel(node.label, 15)}</text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="disposition-graph-detail">
        <section>
          <div className="disposition-section-title">{selectedNode ? "选中实体" : "图谱说明"}</div>
          {selectedNode ? (
            <div className="disposition-detail-card">
              <div className={`disposition-chip type-${selectedNode.type}`}>{nodeTypeLabels[selectedNode.type] ?? selectedNode.type}</div>
              <strong>{selectedNode.label}</strong>
              <p>{selectedNode.summary || "暂无摘要。"}</p>
              {selectedNode.source_page ? (
                <button type="button" onClick={() => onOpenWiki(selectedNode.source_page || "")}>打开依据页面</button>
              ) : null}
            </div>
          ) : (
            <div className="disposition-detail-card">
              <p>单击任一实体可高亮相关关系。图谱从当前会话抽取事故特征、风险、工艺、工具和依据，用于解释最终方案的形成路径。</p>
            </div>
          )}
        </section>
        <section>
          <div className="disposition-section-title">相关关系</div>
          <div className="disposition-relation-list">
            {selectedEdges.slice(0, 10).map((edge, index) => (
              <div className="disposition-relation-row" key={`${edge.source}-${edge.target}-${index}`}>
                <span>{nodeMap.get(edge.source)?.label ?? edge.source}</span>
                <b>{edge.label}</b>
                <span>{nodeMap.get(edge.target)?.label ?? edge.target}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function layoutDispositionGraph(nodes: DispositionGraphNode[]) {
  const columns: Record<string, { x: number; startY: number; gap: number }> = {
    accident: { x: 92, startY: 220, gap: 64 },
    feature: { x: 260, startY: 76, gap: 58 },
    risk: { x: 455, startY: 82, gap: 60 },
    procedure: { x: 650, startY: 70, gap: 60 },
    tool: { x: 850, startY: 120, gap: 58 },
    standard: { x: 1060, startY: 64, gap: 56 },
    case: { x: 1060, startY: 64, gap: 56 },
    synthesis: { x: 1060, startY: 64, gap: 56 },
    evidence: { x: 1060, startY: 64, gap: 56 },
    decision: { x: 850, startY: 520, gap: 58 },
  };
  const evidenceTypes = new Set(["standard", "case", "synthesis", "evidence"]);
  const groups = nodes.reduce<Record<string, DispositionGraphNode[]>>((items, node) => {
    const type = evidenceTypes.has(node.type) ? "evidence" : node.type;
    items[type] = [...(items[type] ?? []), node];
    return items;
  }, {});
  const map = new Map<string, { x: number; y: number }>();
  const maxGroupSize = Math.max(1, ...Object.values(groups).map((group) => group.length));
  const height = Math.max(560, 120 + maxGroupSize * 60);
  const width = 1160;
  Object.entries(groups).forEach(([type, group]) => {
    const column = columns[type] ?? { x: 500, startY: 80, gap: 48 };
    const laneHeight = Math.max(0, (group.length - 1) * column.gap);
    const startY = type === "accident"
      ? Math.max(220, height / 2)
      : type === "decision"
        ? Math.max(520, height - 72)
        : Math.max(column.startY, (height - laneHeight) / 2);
    group.forEach((node, index) => {
      map.set(node.id, { x: column.x, y: startY + index * column.gap });
    });
  });
  return { height, positions: map, width };
}

function nodeWidth(node: DispositionGraphNode) {
  return Math.max(84, Math.min(150, node.label.length * 12 + 18));
}

function shortLabel(label: string, limit: number) {
  return label.length > limit ? `${label.slice(0, limit - 1)}...` : label;
}

export default DispositionGraphPane;
