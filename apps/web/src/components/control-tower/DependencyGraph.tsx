"use client";
import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { NetworkOrder } from "@/lib/network";
const columns: Record<string, number> = {
  Supplier: 0,
  Material: 1,
  Product: 2,
  Order: 3,
  Customer: 4,
};
export default function DependencyGraph({ order }: { order: NetworkOrder }) {
  const graph = useMemo(() => {
    const nodes = new Map<string, Node>(),
      edges = new Map<string, Edge>(),
      counters: Record<string, number> = {};
    order.dependency_paths.forEach((p) =>
      p.nodes.forEach((n, i) => {
        const id = `${n.type}:${n.id}`;
        if (!nodes.has(id)) {
          const y = counters[n.type] || 0;
          counters[n.type] = y + 1;
          nodes.set(id, {
            id,
            position: { x: columns[n.type] * 210, y: y * 90 },
            data: { label: `${n.name}\n${n.id === n.name ? n.type : n.id}` },
            style: {
              width: 170,
              fontSize: 11,
              border: "1px solid #64748b",
              background: "#f8fafc",
              borderRadius: 10,
              whiteSpace: "pre-line",
            },
            sourcePosition: "right" as never,
            targetPosition: "left" as never,
          });
        }
        if (i) {
          const previous = p.nodes[i - 1];
          const source = `${previous.type}:${previous.id}`,
            edgeId = `${source}->${id}`;
          edges.set(edgeId, {
            id: edgeId,
            source,
            target: id,
            label: p.relationships[i - 1],
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: "#0891b2", strokeWidth: 1.5 },
          });
        }
      }),
    );
    return { nodes: [...nodes.values()], edges: [...edges.values()] };
  }, [order]);
  return (
    <div
      className="h-[360px] rounded-xl border border-slate-200 bg-white"
      data-testid="business-dependency"
    >
      <ReactFlow
        nodes={graph.nodes}
        edges={graph.edges}
        fitView
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
