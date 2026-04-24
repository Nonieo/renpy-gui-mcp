import { useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import dagre from "dagre";
import { api } from "@/api/client";
import type { BranchGraph } from "@/api/types";

function layout(graph: BranchGraph, selectedId: string | null): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 30, ranksep: 80 });
  g.setDefaultEdgeLabel(() => ({}));

  const NODE_W = 180;
  const NODE_H = 60;

  for (const n of graph.nodes) {
    g.setNode(n.id, { width: NODE_W, height: NODE_H });
  }
  for (const e of graph.edges) {
    g.setEdge(e.from, e.to);
  }
  dagre.layout(g);

  const nodes: Node[] = graph.nodes.map((n) => {
    const pos = g.node(n.id);
    const isSelected = n.id === selectedId;
    const isStart = n.id === "start";
    return {
      id: n.id,
      position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 },
      data: { label: n.id, sayCount: n.say_count, file: n.file },
      type: "default",
      style: {
        background: isStart ? "#1c1917" : "#ffffff",
        color: isStart ? "#fafaf9" : "#18181b",
        border: isSelected ? "2px solid #6366f1" : "1px solid #d4d4d8",
        boxShadow: isSelected ? "0 0 0 3px rgb(99 102 241 / 0.18)" : undefined,
        borderRadius: 8,
        padding: "8px 14px",
        fontSize: 13,
        fontWeight: 500,
        width: NODE_W,
        cursor: "pointer",
      },
    };
  });

  const edges: Edge[] = graph.edges.map((e, i) => ({
    id: `${e.from}-${e.to}-${i}`,
    source: e.from,
    target: e.to,
    label: e.kind === "call" ? "call" : undefined,
    style: {
      stroke: e.kind === "call" ? "#a855f7" : "#71717a",
      strokeWidth: 1.5,
      strokeDasharray: e.kind === "call" ? "4 4" : undefined,
    },
    labelStyle: { fontSize: 10 },
  }));

  return { nodes, edges };
}

export function StoryMap({
  selectedLabel,
  onSelectLabel,
}: {
  selectedLabel: string | null;
  onSelectLabel: (name: string | null) => void;
}) {
  const graph = useQuery({
    queryKey: ["graph"],
    queryFn: () => api<BranchGraph>("/api/graph"),
  });

  const laidOut = useMemo(
    () => (graph.data ? layout(graph.data, selectedLabel) : null),
    [graph.data, selectedLabel],
  );

  const onNodeClick = useCallback<NodeMouseHandler>(
    (_evt, node) => onSelectLabel(node.id),
    [onSelectLabel],
  );

  if (graph.isLoading) {
    return <div className="p-8 text-sm text-zinc-500">Loading project graph…</div>;
  }
  if (graph.error) {
    return <div className="p-8 text-sm text-red-600">Error: {String(graph.error)}</div>;
  }
  if (!laidOut || laidOut.nodes.length === 0) {
    return <div className="p-8 text-sm text-zinc-500">No labels found in this project.</div>;
  }

  return (
    <div className="rf-shell">
      <ReactFlowProvider>
        <ReactFlow
          nodes={laidOut.nodes}
          edges={laidOut.edges}
          onNodeClick={onNodeClick}
          onPaneClick={() => onSelectLabel(null)}
          nodesDraggable={false}
          nodesConnectable={false}
          fitView
          fitViewOptions={{ padding: 0.15 }}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={24} size={1} color="#e4e4e7" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
