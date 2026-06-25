"use client";

import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  MarkerType,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo } from "react";
import {
  AlertTriangle,
  Box,
  Factory,
  Package,
  ShoppingCart,
  Truck,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

export interface GraphNodeData {
  label: string;
  nodeType: string;
  code: string;
  impactLevel?: "source" | "direct" | "indirect" | "none" | "alternative";
  riskScore?: number;
  [key: string]: unknown;
}

type RawNode = {
  label?: string;
  labels?: string[];
  code?: string;
  name?: string;
  properties?: Record<string, string>;
};

const LAYER_ORDER: Record<string, number> = {
  Supplier: 0,
  RiskEvent: 0,
  Material: 1,
  QualityIssue: 1,
  Product: 2,
  Order: 3,
  DeliveryEvent: 3,
  Customer: 4,
};

const LAYER_X_GAP = 200;
const LAYER_Y_GAP = 100;

function resolveType(raw: RawNode): string {
  return raw.label || raw.labels?.[0] || "Unknown";
}

function resolveCode(raw: RawNode, fallback: string): string {
  const props = raw.properties || {};
  return raw.code || props.code || props.order_no || props.id || fallback;
}

function nodeKey(type: string, code: string): string {
  return `${type}:${code}`;
}

function markImpact(
  code: string,
  type: string,
  sourceCode: string | undefined,
  affectedSets: Record<string, string[] | undefined>,
  alternatives?: string[]
): GraphNodeData["impactLevel"] {
  if (alternatives?.includes(code)) return "alternative";
  if (sourceCode && code === sourceCode && (type === "Supplier" || type === "Order")) return "source";
  const sets: [string[] | undefined, string][] = [
    [affectedSets.suppliers, "Supplier"],
    [affectedSets.materials, "Material"],
    [affectedSets.products, "Product"],
    [affectedSets.orders, "Order"],
    [affectedSets.customers, "Customer"],
  ];
  for (const [list, t] of sets) {
    if (list?.includes(code) && type === t) return "direct";
  }
  if (sourceCode && type !== "Supplier") return "indirect";
  return "none";
}

function buildFromPaths(
  graphPaths: {
    nodes?: RawNode[];
    relationships?: { type?: string }[];
  }[],
  affectedSets: {
    suppliers?: string[];
    materials?: string[];
    products?: string[];
    orders?: string[];
    customers?: string[];
  },
  sourceCode?: string,
  variant: "classic" | "propagation" = "classic"
) {
  const nodeMap = new Map<string, GraphNodeData>();
  const edgeSet = new Set<string>();
  const edges: Edge[] = [];
  const alternatives = affectedSets.suppliers?.filter((c) => c !== sourceCode) || [];

  graphPaths.forEach((path, pi) => {
    const nodes = path.nodes || [];
    nodes.forEach((n, ni) => {
      const type = resolveType(n);
      const code = resolveCode(n, `${type}-${pi}-${ni}`);
      const id = nodeKey(type, code);
      if (!nodeMap.has(id)) {
        nodeMap.set(id, {
          label: n.name || n.properties?.name || n.properties?.title || code,
          nodeType: type,
          code,
          impactLevel: markImpact(code, type, sourceCode, affectedSets, alternatives),
        });
      }
      if (ni > 0) {
        const prev = nodes[ni - 1];
        const prevType = resolveType(prev);
        const prevCode = resolveCode(prev, `${prevType}-${pi}-${ni - 1}`);
        const prevId = nodeKey(prevType, prevCode);
        const edgeId = `${prevId}->${id}:${pi}`;
        if (!edgeSet.has(edgeId)) {
          edgeSet.add(edgeId);
          const targetImpact = nodeMap.get(id)?.impactLevel || "none";
          const stroke = propagationEdgeColor(targetImpact, variant);
          edges.push({
            id: edgeId,
            source: prevId,
            target: id,
            label: variant === "classic" ? path.relationships?.[ni - 1]?.type || "LINK" : undefined,
            animated: targetImpact !== "none",
            style: {
              stroke,
              strokeWidth: variant === "propagation" ? 2.5 : 2,
              strokeDasharray: variant === "propagation" ? "6 6" : undefined,
            },
            markerEnd: {
              type: MarkerType.ArrowClosed,
              color: stroke,
            },
          });
        }
      }
    });
  });

  const layerBuckets = new Map<number, string[]>();
  for (const id of nodeMap.keys()) {
    const data = nodeMap.get(id)!;
    const layer =
      data.impactLevel === "source" ? 0 : LAYER_ORDER[data.nodeType] ?? 2;
    if (!layerBuckets.has(layer)) layerBuckets.set(layer, []);
    layerBuckets.get(layer)!.push(id);
  }

  const flowNodes: Node[] = [];
  for (const [layer, ids] of layerBuckets.entries()) {
    ids.forEach((id, idx) => {
      const data = nodeMap.get(id)!;
      const isAlt = data.impactLevel === "alternative";
      flowNodes.push({
        id,
        type: variant === "propagation" ? "propagation" : "supply",
        position: {
          x: layer * LAYER_X_GAP,
          y: isAlt ? (ids.length + 1) * LAYER_Y_GAP : idx * LAYER_Y_GAP,
        },
        data,
      });
    });
  }

  return { nodes: flowNodes, edges };
}

function propagationEdgeColor(impact: GraphNodeData["impactLevel"], variant: string): string {
  if (variant !== "propagation") {
    return impact !== "none" ? "#f97316" : "#cbd5e1";
  }
  switch (impact) {
    case "source":
      return "#ef4444";
    case "direct":
      return "#f97316";
    case "indirect":
      return "#3b82f6";
    case "alternative":
      return "#22c55e";
    default:
      return "#64748b";
  }
}

function minimapNodeColor(data: GraphNodeData): string {
  switch (data.impactLevel) {
    case "source":
      return "#ef4444";
    case "direct":
      return "#f97316";
    case "alternative":
      return "#22c55e";
    case "indirect":
      return "#3b82f6";
    default:
      return data.nodeType === "Product" ? "#a78bfa" : "#64748b";
  }
}

function propagationNodeStyle(data: GraphNodeData) {
  switch (data.impactLevel) {
    case "source":
      return {
        ring: "ring-2 ring-red-400 shadow-[0_0_20px_rgba(239,68,68,0.55)] bg-red-950/80",
        icon: "text-red-300",
        dot: "bg-red-500",
      };
    case "direct":
      return {
        ring: "ring-2 ring-orange-400 shadow-[0_0_16px_rgba(249,115,22,0.45)] bg-orange-950/70",
        icon: "text-orange-300",
        dot: "bg-orange-500",
      };
    case "alternative":
      return {
        ring: "ring-2 ring-green-400 shadow-[0_0_16px_rgba(34,197,94,0.45)] bg-green-950/70",
        icon: "text-green-300",
        dot: "bg-green-500",
      };
    case "indirect":
      return {
        ring: "ring-2 ring-blue-400 shadow-[0_0_14px_rgba(59,130,246,0.4)] bg-blue-950/70",
        icon: "text-blue-300",
        dot: "bg-blue-500",
      };
    default:
      if (data.nodeType === "Product") {
        return {
          ring: "ring-2 ring-violet-400 shadow-[0_0_14px_rgba(167,139,250,0.4)] bg-violet-950/70",
          icon: "text-violet-300",
          dot: "bg-violet-500",
        };
      }
      return {
        ring: "ring-2 ring-slate-500 shadow-[0_0_10px_rgba(100,116,139,0.3)] bg-slate-900/80",
        icon: "text-slate-300",
        dot: "bg-slate-500",
      };
  }
}

function NodeIcon({ type }: { type: string }) {
  const cls = "h-6 w-6";
  switch (type) {
    case "Supplier":
      return <Factory className={cls} />;
    case "Material":
      return <Box className={cls} />;
    case "Product":
      return <Package className={cls} />;
    case "Order":
      return <ShoppingCart className={cls} />;
    case "Customer":
      return <Users className={cls} />;
    case "RiskEvent":
    case "QualityIssue":
      return <AlertTriangle className={cls} />;
    case "DeliveryEvent":
      return <Truck className={cls} />;
    default:
      return <Box className={cls} />;
  }
}

function PropagationNode({ data }: { data: GraphNodeData }) {
  const style = propagationNodeStyle(data);
  return (
    <div className="flex flex-col items-center min-w-[100px] max-w-[120px]">
      <div
        className={cn(
          "flex h-[72px] w-[72px] items-center justify-center rounded-full backdrop-blur-sm",
          style.ring
        )}
      >
        <div className={style.icon}>
          <NodeIcon type={data.nodeType} />
        </div>
      </div>
      <p className="mt-2 text-center text-[11px] font-semibold text-slate-100 leading-tight">{data.code}</p>
      <p className="mt-0.5 text-center text-[10px] text-slate-400 line-clamp-2">{data.label}</p>
    </div>
  );
}

const nodeColors: Record<string, string> = {
  Supplier: "#7c3aed",
  Material: "#0891b2",
  Product: "#16a34a",
  Order: "#ea580c",
  Customer: "#db2777",
};

function SupplyNodeClassic({ data }: { data: GraphNodeData }) {
  const color = nodeColors[data.nodeType] || "#64748b";
  return (
    <div
      className={cn(
        "rounded-lg border bg-white px-3 py-2 shadow-sm min-w-[120px]",
        data.impactLevel === "source" && "ring-4 ring-red-500 animate-pulse-risk",
        data.impactLevel === "direct" && "ring-2 ring-orange-400",
        data.impactLevel === "alternative" && "ring-2 ring-green-500"
      )}
      style={{ borderLeftColor: color, borderLeftWidth: 4 }}
    >
      <p className="text-[10px] font-medium text-slate-400 uppercase">{data.nodeType}</p>
      <p className="text-sm font-semibold text-slate-800">{data.code}</p>
      <p className="text-xs text-slate-500 truncate max-w-[140px]">{data.label}</p>
    </div>
  );
}

const nodeTypes = { supply: SupplyNodeClassic, propagation: PropagationNode };

function PropagationLegend() {
  const items = [
    { color: "bg-red-500", label: "风险源" },
    { color: "bg-orange-500", label: "受影响核心体" },
    { color: "bg-violet-500", label: "关键产品" },
    { color: "bg-blue-500", label: "终端客户/订单" },
    { color: "bg-green-500", label: "替代供应商" },
  ];
  return (
    <div className="absolute bottom-3 left-3 right-3 z-10 flex flex-wrap items-center justify-center gap-4 rounded-lg border border-slate-700/80 bg-slate-900/90 px-4 py-2 text-[11px] text-slate-300">
      <span className="font-medium text-slate-200">供应链影响扩散</span>
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <span className={cn("h-2.5 w-2.5 rounded-full", item.color)} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

export function SupplyChainGraph({
  graphPaths,
  affected,
  sourceCode,
  className,
  variant = "classic",
  title,
}: {
  graphPaths: Record<string, unknown>[];
  affected: Record<string, string[]>;
  sourceCode?: string;
  className?: string;
  variant?: "classic" | "propagation";
  title?: string;
}) {
  const { nodes: flowNodes, edges: flowEdges } = useMemo(
    () =>
      buildFromPaths(
        graphPaths as Parameters<typeof buildFromPaths>[0],
        affected,
        sourceCode,
        variant
      ),
    [graphPaths, affected, sourceCode, variant]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  if (!flowNodes.length) {
    return (
      <div
        className={cn(
          "flex h-full items-center justify-center text-sm",
          variant === "propagation" ? "text-slate-500 bg-slate-950 rounded-xl" : "text-slate-400",
          className
        )}
      >
        {variant === "propagation" ? "运行 GraphRAG 查询以展示供应链传播图" : "Run impact simulation to visualize the supply chain graph"}
      </div>
    );
  }

  const isPropagation = variant === "propagation";

  return (
    <div
      className={cn(
        "relative h-full w-full rounded-xl border overflow-hidden",
        isPropagation ? "border-slate-700 bg-slate-950" : "border-slate-200 bg-slate-50",
        className
      )}
    >
      {isPropagation && title && (
        <div className="absolute top-3 left-0 right-0 z-10 text-center pointer-events-none">
          <p className="text-sm font-semibold text-slate-100">{title}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">风险沿供应链路径逐级扩散</p>
        </div>
      )}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.8}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={isPropagation ? BackgroundVariant.Dots : BackgroundVariant.Lines}
          gap={isPropagation ? 20 : 16}
          color={isPropagation ? "#334155" : "#e2e8f0"}
        />
        <Controls className={isPropagation ? "!bg-slate-800 !border-slate-600 [&>button]:!bg-slate-800 [&>button]:!text-slate-200 [&>button]:!border-slate-600" : undefined} />
        {isPropagation ? (
          <MiniMap
            nodeColor={(n) => minimapNodeColor(n.data as GraphNodeData)}
            maskColor="rgb(15 23 42 / 0.8)"
            className="!bg-slate-900 !border-slate-700"
          />
        ) : (
          <MiniMap nodeColor={(n) => nodeColors[(n.data as GraphNodeData).nodeType] || "#94a3b8"} />
        )}
      </ReactFlow>
      {isPropagation && <PropagationLegend />}
    </div>
  );
}
