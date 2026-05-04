/*
 * Build xyflow nodes + edges from the current turn's code_core.* artifacts
 * AND from the explored pool the user has populated by clicking nodes.
 *
 * Each edge carries a `relKind` tag (inheritance | calls | semantic) so
 * GraphPane can switch between relationship views without re-fetching.
 *
 * Per-category fan-out is capped to keep the canvas in the 30–40 node band
 * the user asked for; overflow is dropped after a degree-based prune.
 */
import {Edge, Node} from "@xyflow/react";
import dagre from "dagre";

import {CodeCoreArtifact} from "../../../features/logExtensions/codeCore/types.ts";
import {
    ALL_FOOTPRINT_SLICES,
    FootprintSlice,
} from "../../../features/configAssistant/configAssistantSlice.ts";

export type SemanticNodeKind = "class" | "concept" | "policy" | "callsite";

export type RelKind = "inheritance" | "calls" | "semantic";

export type SemanticNodeData = {
    label: string;
    sub?: string;
    kind: SemanticNodeKind;
    qualifiedName?: string;
    conceptId?: string;
    /** True when this node is one the user explicitly opened (vs. a neighbour). */
    focal?: boolean;
};

const STYLE: Record<SemanticNodeKind, React.CSSProperties> = {
    class: {
        background: "#dbeafe",
        border: "1px solid #2563eb",
        color: "#1e3a8a",
        borderRadius: 8,
        padding: 10,
        fontSize: 12,
        minWidth: 160,
    },
    concept: {
        background: "#fef3c7",
        border: "1px dashed #d97706",
        color: "#78350f",
        borderRadius: 999,
        padding: "8px 14px",
        fontSize: 12,
        fontStyle: "italic",
        minWidth: 140,
    },
    policy: {
        background: "#ede9fe",
        border: "1px dashed #7c3aed",
        color: "#4c1d95",
        borderRadius: 999,
        padding: "8px 14px",
        fontSize: 12,
        fontStyle: "italic",
        minWidth: 140,
    },
    callsite: {
        background: "#f1f5f9",
        border: "1px solid #64748b",
        color: "#1e293b",
        borderRadius: 6,
        padding: "6px 10px",
        fontSize: 11,
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
        minWidth: 140,
    },
};

const NODE_WIDTH: Record<SemanticNodeKind, number> = {
    class: 200,
    concept: 180,
    policy: 200,
    callsite: 200,
};
const NODE_HEIGHT: Record<SemanticNodeKind, number> = {
    class: 56,
    concept: 44,
    policy: 44,
    callsite: 36,
};

// Per-category fan-out for one ingested source. Tighter on the noisy
// categories (callers/callees/descendants can blow past 30 in a real graph).
const MAX_RELATED = 4;
const MAX_REALIZED = 4;
const MAX_APPLIED = 4;
const MAX_CONCEPTS = 4;
const MAX_POLICIES = 4;
const MAX_ANCESTORS = 4;
const MAX_DESCENDANTS = 4;
const MAX_CALLERS = 5;
const MAX_CALLEES = 5;

// Hard cap on canvas nodes — user spec is 30–40.
const MAX_NODES = 35;

interface MutableGraph {
    nodes: Map<string, Node<SemanticNodeData>>;
    edges: Map<string, EdgeWithKind>;
}

interface EdgeWithKind extends Edge {
    relKind: RelKind;
}

const ensureNode = (
    g: MutableGraph,
    id: string,
    data: SemanticNodeData,
): void => {
    const existing = g.nodes.get(id);
    if (existing) {
        // Promote to focal if either side asked for it — focal status
        // protects the node when we hit the 35-node cap.
        if (data.focal && !existing.data.focal) {
            existing.data = {...existing.data, focal: true};
        }
        return;
    }
    g.nodes.set(id, {
        id,
        position: {x: 0, y: 0}, // dagre fills this in below
        data,
        style: STYLE[data.kind],
    });
};

const EDGE_PRESETS: Record<
    "embodies" | "governed_by" | "related" | "inherits" | "inherited_by"
        | "realized_by" | "calls" | "called_by",
    {edge: React.CSSProperties; animated: boolean; relKind: RelKind}
> = {
    embodies:     {edge: {stroke: "#d97706", strokeDasharray: "6 4"}, animated: true,  relKind: "semantic"},
    governed_by:  {edge: {stroke: "#7c3aed", strokeDasharray: "6 4"}, animated: false, relKind: "semantic"},
    related:      {edge: {stroke: "#d97706"},                          animated: false, relKind: "semantic"},
    inherits:     {edge: {stroke: "#2563eb"},                          animated: false, relKind: "inheritance"},
    inherited_by: {edge: {stroke: "#2563eb", strokeDasharray: "4 3"},  animated: false, relKind: "inheritance"},
    realized_by:  {edge: {stroke: "#d97706", strokeDasharray: "6 4"}, animated: true,  relKind: "semantic"},
    calls:        {edge: {stroke: "#0f766e"},                          animated: true,  relKind: "calls"},
    called_by:    {edge: {stroke: "#0f766e", strokeDasharray: "4 3"},  animated: true,  relKind: "calls"},
};

const ensureEdge = (
    g: MutableGraph,
    id: string,
    source: string,
    target: string,
    label: string,
    style: keyof typeof EDGE_PRESETS,
): void => {
    if (g.edges.has(id)) return;
    const preset = EDGE_PRESETS[style];
    g.edges.set(id, {
        id,
        source,
        target,
        label,
        animated: preset.animated,
        style: preset.edge,
        labelStyle: {fontSize: 10, fill: "#475569"},
        relKind: preset.relKind,
    });
};

const shortName = (qn: string): string => {
    if (!qn) return qn;
    const parts = qn.split(".");
    return parts[parts.length - 1] || qn;
};

/**
 * Heuristic: callers / callees in CLASS_FOOTPRINT can be Method or Function
 * nodes (qualified_name shaped `pkg.Module.Class.method` or `pkg.Module.func`).
 * We render them as compact callsite pills so they don't compete visually
 * with first-class Class boxes.
 */
const ingestDefine = (
    g: MutableGraph,
    payload: Record<string, unknown> | null | undefined,
): void => {
    if (!payload || !Array.isArray(payload.matches)) return;
    const match = (payload.matches as Array<Record<string, unknown>>)[0];
    if (!match) return;

    const id = `concept:${match.id}`;
    const isPolicy = match.kind === "policy";
    const focalKind: SemanticNodeKind = isPolicy ? "policy" : "concept";

    ensureNode(g, id, {
        label: String(match.name ?? match.id ?? "Concept"),
        sub: isPolicy ? "policy" : "concept",
        kind: focalKind,
        conceptId: String(match.id ?? ""),
        focal: true,
    });

    const related = Array.isArray(match.related)
        ? (match.related as Array<Record<string, unknown>>).slice(0, MAX_RELATED)
        : [];
    const realized = Array.isArray(match.realized_by)
        ? (match.realized_by as string[]).slice(0, MAX_REALIZED)
        : [];
    const applied = Array.isArray(match.applied_to)
        ? (match.applied_to as string[]).slice(0, MAX_APPLIED)
        : [];

    for (const rel of related) {
        if (!rel.id) continue;
        const relId = `concept:${rel.id}`;
        ensureNode(g, relId, {
            label: String(rel.name ?? rel.id ?? "Concept"),
            sub: rel.kind === "policy" ? "policy" : "concept",
            kind: rel.kind === "policy" ? "policy" : "concept",
            conceptId: String(rel.id ?? ""),
        });
        ensureEdge(g, `${id}->${relId}:related`, id, relId, "RELATED_TO", "related");
    }

    for (const qn of realized) {
        if (!qn) continue;
        const cid = `class:${qn}`;
        ensureNode(g, cid, {
            label: shortName(qn),
            sub: "class",
            kind: "class",
            qualifiedName: qn,
        });
        ensureEdge(g, `${id}->${cid}:realized_by`, id, cid, "REALIZED_BY", "realized_by");
    }

    for (const qn of applied) {
        if (!qn) continue;
        const cid = `class:${qn}`;
        ensureNode(g, cid, {
            label: shortName(qn),
            sub: "class",
            kind: "class",
            qualifiedName: qn,
        });
        ensureEdge(g, `${cid}->${id}:governed_by`, cid, id, "GOVERNED_BY", "governed_by");
    }
};

const ingestClassFootprint = (
    g: MutableGraph,
    payload: Record<string, unknown> | null | undefined,
    enabledSlices: ReadonlySet<FootprintSlice>,
): void => {
    if (!payload || !Array.isArray(payload.footprint)) return;
    const fp = (payload.footprint as Array<Record<string, unknown>>)[0];
    if (!fp || !fp.qualified_name) return;
    const qn = String(fp.qualified_name);
    const id = `class:${qn}`;

    ensureNode(g, id, {
        label: String(fp.name ?? shortName(qn)),
        sub: "class",
        kind: "class",
        qualifiedName: qn,
        focal: true,
    });

    const concepts = enabledSlices.has("concepts") && Array.isArray(payload.concepts)
        ? (payload.concepts as Array<Record<string, unknown>>).slice(0, MAX_CONCEPTS)
        : [];
    const policies = enabledSlices.has("policies") && Array.isArray(payload.style_policies)
        ? (payload.style_policies as Array<Record<string, unknown>>).slice(0, MAX_POLICIES)
        : [];
    const ancestors = enabledSlices.has("ancestors") && Array.isArray(fp.ancestors)
        ? (fp.ancestors as string[]).filter(Boolean).slice(0, MAX_ANCESTORS)
        : [];
    const descendants = enabledSlices.has("descendants") && Array.isArray(fp.descendants)
        ? (fp.descendants as string[]).filter(Boolean).slice(0, MAX_DESCENDANTS)
        : [];
    const callers = enabledSlices.has("callers") && Array.isArray(fp.callers)
        ? (fp.callers as string[]).filter(Boolean).slice(0, MAX_CALLERS)
        : [];
    const callees = enabledSlices.has("callees") && Array.isArray(fp.callees)
        ? (fp.callees as string[]).filter(Boolean).slice(0, MAX_CALLEES)
        : [];

    for (const c of concepts) {
        if (!c.id) continue;
        const cid = `concept:${c.id}`;
        ensureNode(g, cid, {
            label: String(c.name ?? c.id ?? "Concept"),
            sub: "concept",
            kind: "concept",
            conceptId: String(c.id ?? ""),
        });
        ensureEdge(g, `${id}->${cid}:embodies`, id, cid, "EMBODIES", "embodies");
    }

    for (const p of policies) {
        if (!p.id) continue;
        const pid = `policy:${p.id}`;
        ensureNode(g, pid, {
            label: String(p.name ?? p.id ?? "Policy"),
            sub: "policy",
            kind: "policy",
            conceptId: String(p.id ?? ""),
        });
        ensureEdge(g, `${id}->${pid}:governed_by`, id, pid, "GOVERNED_BY", "governed_by");
    }

    for (const ancestorQn of ancestors) {
        const aid = `class:${ancestorQn}`;
        ensureNode(g, aid, {
            label: shortName(ancestorQn),
            sub: "class",
            kind: "class",
            qualifiedName: ancestorQn,
        });
        ensureEdge(g, `${id}->${aid}:inherits`, id, aid, "INHERITS", "inherits");
    }

    for (const descendantQn of descendants) {
        const did = `class:${descendantQn}`;
        ensureNode(g, did, {
            label: shortName(descendantQn),
            sub: "class",
            kind: "class",
            qualifiedName: descendantQn,
        });
        ensureEdge(g, `${did}->${id}:inherits`, did, id, "INHERITED_BY", "inherited_by");
    }

    for (const callerQn of callers) {
        const sid = `callsite:${callerQn}`;
        ensureNode(g, sid, {
            label: shortName(callerQn),
            sub: "calls →",
            kind: "callsite",
            qualifiedName: callerQn,
        });
        ensureEdge(g, `${sid}->${id}:called_by`, sid, id, "CALLS", "called_by");
    }

    for (const calleeQn of callees) {
        const sid = `callsite:${calleeQn}`;
        ensureNode(g, sid, {
            label: shortName(calleeQn),
            sub: "→ calls",
            kind: "callsite",
            qualifiedName: calleeQn,
        });
        ensureEdge(g, `${id}->${sid}:calls`, id, sid, "CALLS", "calls");
    }
};

export interface BuiltGraph {
    nodes: Node<SemanticNodeData>[];
    edges: Edge[];
}

const layoutWithDagre = (
    nodes: Node<SemanticNodeData>[],
    edges: Edge[],
): Node<SemanticNodeData>[] => {
    if (!nodes.length) return nodes;
    const dg = new dagre.graphlib.Graph();
    dg.setGraph({rankdir: "TB", nodesep: 38, ranksep: 70, marginx: 20, marginy: 20});
    dg.setDefaultEdgeLabel(() => ({}));

    for (const n of nodes) {
        dg.setNode(n.id, {
            width: NODE_WIDTH[n.data.kind],
            height: NODE_HEIGHT[n.data.kind],
        });
    }
    for (const e of edges) {
        dg.setEdge(e.source, e.target);
    }

    dagre.layout(dg);

    return nodes.map((n) => {
        const meta = dg.node(n.id);
        if (!meta) return n;
        return {
            ...n,
            position: {
                x: meta.x - NODE_WIDTH[n.data.kind] / 2,
                y: meta.y - NODE_HEIGHT[n.data.kind] / 2,
            },
        };
    });
};

/**
 * Drop low-value non-focal nodes when the graph would exceed MAX_NODES.
 * Lowest-degree non-focal nodes go first; focal nodes (the ones the user
 * explicitly opened) are always kept.
 */
const trimToMax = (g: MutableGraph): void => {
    if (g.nodes.size <= MAX_NODES) return;
    const degree = new Map<string, number>();
    for (const e of g.edges.values()) {
        degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
        degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
    }
    const candidates = [...g.nodes.values()]
        .filter((n) => !n.data.focal)
        .sort((a, b) => (degree.get(a.id) ?? 0) - (degree.get(b.id) ?? 0));
    const surplus = g.nodes.size - MAX_NODES;
    for (let i = 0; i < surplus && i < candidates.length; i++) {
        const id = candidates[i].id;
        g.nodes.delete(id);
        for (const [eid, e] of g.edges) {
            if (e.source === id || e.target === id) g.edges.delete(eid);
        }
    }
};

export interface GraphInputSource {
    kind: string;
    payload: Record<string, unknown> | null;
    /** For class_footprint sources, which slices to render. Ignored for define. */
    enabledSlices?: ReadonlySet<FootprintSlice>;
}

const DEFAULT_SLICES: ReadonlySet<FootprintSlice> = new Set(ALL_FOOTPRINT_SLICES);

export function buildGraphFromArtifacts(
    artifacts: ReadonlyArray<CodeCoreArtifact>,
): BuiltGraph {
    return buildGraphFromSources(artifacts.map((a) => ({
        kind: a.content.kind,
        payload: a.content.payload as Record<string, unknown> | null,
    })));
}

export function buildGraphFromSources(
    sources: ReadonlyArray<GraphInputSource>,
): BuiltGraph {
    const g: MutableGraph = {
        nodes: new Map(),
        edges: new Map(),
    };

    for (const a of sources) {
        const payload = a.payload;
        switch (a.kind) {
            case "define":
                ingestDefine(g, payload);
                break;
            case "class_footprint":
                ingestClassFootprint(g, payload, a.enabledSlices ?? DEFAULT_SLICES);
                break;
            default:
                break;
        }
    }

    trimToMax(g);

    const rawNodes = Array.from(g.nodes.values());
    const edges: Edge[] = Array.from(g.edges.values());
    return {
        nodes: layoutWithDagre(rawNodes, edges),
        edges,
    };
}

export function buildGraphCombined(
    artifacts: ReadonlyArray<CodeCoreArtifact>,
    exploredDefines: Record<string, unknown>,
    exploredFootprints: Record<string, unknown>,
    expandedSlices: Record<string, FootprintSlice[]>,
): BuiltGraph {
    const sources: GraphInputSource[] = [];
    for (const a of artifacts) {
        sources.push({
            kind: a.content.kind,
            payload: a.content.payload as Record<string, unknown> | null,
        });
    }
    for (const data of Object.values(exploredDefines)) {
        sources.push({kind: "define", payload: data as Record<string, unknown> | null});
    }
    for (const [qn, data] of Object.entries(exploredFootprints)) {
        const slices = expandedSlices[qn];
        sources.push({
            kind: "class_footprint",
            payload: data as Record<string, unknown> | null,
            enabledSlices: slices ? new Set(slices) : DEFAULT_SLICES,
        });
    }
    return buildGraphFromSources(sources);
}

export const NODE_STYLE = STYLE;

/** Read the relKind tag we attach to every edge in EDGE_PRESETS. */
export const edgeRelKind = (edge: Edge): RelKind | null => {
    const tag = (edge as Edge & {relKind?: RelKind}).relKind;
    return tag ?? null;
};
