/*
 * SPDX-License-Identifier: MIT
 * GraphPane — top pane of the Configuration Assistant inspect column.
 *
 * The graph is built from two sources:
 *   1. code_core.* artifacts emitted by the agent in the current turn
 *   2. the explored pool — everything the user has clicked + the lookup
 *      hooks have fetched directly via /api/integrations/code-core/*
 *
 * Each edge is tagged with a `relKind` (inheritance | calls | semantic)
 * so the user can switch lenses without re-fetching anything.
 */
import {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {
    Background,
    BackgroundVariant,
    Controls,
    Edge,
    Node,
    ReactFlow,
    type NodeMouseHandler,
    type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {useAppDispatch, useAppSelector} from "../../../app/store.ts";
import {selectLatestTurn} from "../../../features/chat/chatStateSlice.ts";
import {
    RelationshipFilter,
    selectClass,
    selectConcept,
    selectConfigAssistantExpandedSlices,
    selectConfigAssistantExplored,
    selectConfigAssistantRelationshipFilter,
    selectConfigAssistantSelection,
    setRelationshipFilter,
} from "../../../features/configAssistant/configAssistantSlice.ts";
import {
    CODE_CORE_ARTIFACT_TYPE,
    CodeCoreArtifact,
} from "../../../features/logExtensions/codeCore/types.ts";
import {
    BuiltGraph,
    edgeRelKind,
    NODE_STYLE,
    SemanticNodeData,
    buildGraphCombined,
} from "./buildGraph.ts";
import {CodeSearchHit, fetchCodeSearch} from "../codeCoreService.ts";

const DEMO: BuiltGraph = {
    nodes: [
        {
            id: "concept:bundle",
            position: {x: 40, y: 40},
            data: {label: "Bundle", sub: "concept", kind: "concept", conceptId: "bundle"},
            style: NODE_STYLE.concept,
        },
        {
            id: "concept:bundle_entrypoint",
            position: {x: 280, y: 40},
            data: {label: "Bundle Entrypoint", sub: "concept", kind: "concept", conceptId: "bundle_entrypoint"},
            style: NODE_STYLE.concept,
        },
        {
            id: "concept:knowledge_space",
            position: {x: 40, y: 200},
            data: {label: "Knowledge Space", sub: "concept", kind: "concept", conceptId: "knowledge_space"},
            style: NODE_STYLE.concept,
        },
        {
            id: "class:BaseEntrypoint",
            position: {x: 280, y: 200},
            data: {
                label: "BaseEntrypoint",
                sub: "class · demo",
                kind: "class",
                qualifiedName: "kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint.BaseEntrypoint",
            },
            style: NODE_STYLE.class,
        },
    ],
    edges: [
        {
            id: "demo:e1",
            source: "concept:bundle",
            target: "concept:bundle_entrypoint",
            label: "RELATED_TO",
            style: {stroke: "#d97706"},
            labelStyle: {fontSize: 10, fill: "#92400e"},
            ...{relKind: "semantic"},
        },
        {
            id: "demo:e2",
            source: "class:BaseEntrypoint",
            target: "concept:bundle_entrypoint",
            label: "EMBODIES",
            animated: true,
            style: {stroke: "#d97706", strokeDasharray: "6 4"},
            labelStyle: {fontSize: 10, fill: "#92400e"},
            ...{relKind: "semantic"},
        },
    ],
};

const REL_FILTERS: ReadonlyArray<{id: RelationshipFilter; label: string; hint: string}> = [
    {id: "all", label: "All", hint: "Show every relationship type"},
    {id: "inheritance", label: "Inheritance", hint: "INHERITS / INHERITED_BY"},
    {id: "calls", label: "Calls", hint: "CALLS / CALLED_BY"},
    {id: "semantic", label: "Concepts & policies", hint: "EMBODIES / GOVERNED_BY / RELATED_TO / REALIZED_BY"},
];

/**
 * Seed input — lets the user start exploring without an agent turn.
 * Hits /api/integrations/code-core/search (hybrid mode) on debounced
 * change. Picking a hit dispatches selectClass(qn) which triggers
 * useFootprintLookup, which fetches the footprint, populates the
 * explored pool, and the graph grows from that focal class.
 */
function SeedSearchBar() {
    const dispatch = useAppDispatch();
    const [query, setQuery] = useState("");
    const [hits, setHits] = useState<CodeSearchHit[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [open, setOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // Debounced search — fire 220ms after the user stops typing. The
    // ref guards against stale results overwriting fresh ones when the
    // user types fast and earlier requests resolve later.
    const reqId = useRef(0);
    useEffect(() => {
        const trimmed = query.trim();
        if (trimmed.length < 2) {
            setHits([]);
            setError(null);
            setLoading(false);
            return;
        }
        const id = ++reqId.current;
        setLoading(true);
        const handle = window.setTimeout(() => {
            fetchCodeSearch(trimmed, 8, "hybrid")
                .then((res) => {
                    if (id !== reqId.current) return;
                    setHits(res.results ?? []);
                    setError(null);
                    setLoading(false);
                })
                .catch((err: Error) => {
                    if (id !== reqId.current) return;
                    setHits([]);
                    setError(err.message);
                    setLoading(false);
                });
        }, 220);
        return () => window.clearTimeout(handle);
    }, [query]);

    // Outside-click closes the result list so it stops shadowing the canvas.
    useEffect(() => {
        if (!open) return;
        const onDocClick = (evt: MouseEvent) => {
            if (!containerRef.current) return;
            if (!containerRef.current.contains(evt.target as Element)) setOpen(false);
        };
        document.addEventListener("mousedown", onDocClick);
        return () => document.removeEventListener("mousedown", onDocClick);
    }, [open]);

    const onPick = useCallback(
        (hit: CodeSearchHit) => {
            const qn = hit.qualified_name;
            if (!qn) return;
            dispatch(selectClass(qn));
            setOpen(false);
            setQuery("");
            setHits([]);
        },
        [dispatch],
    );

    return (
        <div ref={containerRef} className="relative px-3 py-1.5 border-b border-slate-200 bg-white">
            <input
                type="text"
                value={query}
                onChange={(e) => {
                    setQuery(e.target.value);
                    setOpen(true);
                }}
                onFocus={() => setOpen(true)}
                placeholder="Search classes / methods to seed the graph…"
                className="w-full text-xs px-2 py-1 rounded border border-slate-300 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200"
            />
            {open && (loading || error || hits.length > 0) && (
                <div className="absolute left-3 right-3 top-full mt-1 z-40 max-h-60 overflow-y-auto rounded border border-slate-300 bg-white shadow-lg">
                    {loading && (
                        <div className="px-2 py-1 text-[11px] text-slate-500 italic">Searching…</div>
                    )}
                    {error && !loading && (
                        <div className="px-2 py-1 text-[11px] text-rose-600">Search failed: {error}</div>
                    )}
                    {!loading && !error && hits.length === 0 && (
                        <div className="px-2 py-1 text-[11px] text-slate-500 italic">No matches.</div>
                    )}
                    {!loading && hits.map((h) => (
                        <button
                            key={`${h.qualified_name ?? h.name}-${h.source ?? ""}`}
                            type="button"
                            onMouseDown={(e) => {
                                // mousedown so the click registers before the input loses focus
                                e.preventDefault();
                                onPick(h);
                            }}
                            className="block w-full text-left px-2 py-1 text-[11px] hover:bg-blue-50 border-b last:border-b-0 border-slate-100"
                        >
                            <div className="flex items-center gap-1">
                                <span className="font-medium text-slate-800">{h.name ?? h.qualified_name}</span>
                                {h.kind && (
                                    <span className="text-[9px] uppercase text-slate-500">{h.kind}</span>
                                )}
                                {typeof h.score === "number" && (
                                    <span className="ml-auto text-[9px] text-slate-400">
                                        {h.score.toFixed(2)}
                                    </span>
                                )}
                            </div>
                            <div className="font-mono text-[10px] text-slate-500 break-all">
                                {h.qualified_name}
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

function GraphPane() {
    const dispatch = useAppDispatch();
    const relationshipFilter = useAppSelector(selectConfigAssistantRelationshipFilter);
    const selection = useAppSelector(selectConfigAssistantSelection);
    const latestTurn = useAppSelector(selectLatestTurn);
    const explored = useAppSelector(selectConfigAssistantExplored);
    const expandedSlices = useAppSelector(selectConfigAssistantExpandedSlices);

    const live = useMemo<BuiltGraph>(() => {
        const artifacts = (latestTurn?.artifacts ?? []).filter(
            (a): a is CodeCoreArtifact => a.artifactType === CODE_CORE_ARTIFACT_TYPE,
        );
        const exploredDefines = explored.defines;
        const exploredFootprints = explored.footprints;
        const hasAny =
            artifacts.length > 0
            || Object.keys(exploredDefines).length > 0
            || Object.keys(exploredFootprints).length > 0;
        if (!hasAny) return DEMO;
        return buildGraphCombined(artifacts, exploredDefines, exploredFootprints, expandedSlices);
    }, [latestTurn, explored, expandedSlices]);

    const visible = useMemo(() => {
        const selectedId = selection.kind === "class"
            ? `class:${selection.qualifiedName}`
            : selection.kind === "concept" || selection.kind === "policy"
                ? `concept:${selection.conceptId}`
                : null;

        // Step 1 — filter edges by the active relationship lens.
        const edges: Edge[] = relationshipFilter === "all"
            ? live.edges
            : live.edges.filter((e) => edgeRelKind(e) === relationshipFilter);

        // Step 2 — pick which nodes survive.
        //   · "all"     -> keep everything (orphan nodes from earlier explorations
        //                  must stay visible — they're the user's history).
        //   · narrow    -> keep focal nodes + endpoints of surviving edges, so the
        //                  canvas doesn't dangle disconnected neighbours when the
        //                  user is asking "show me only the calls graph".
        const keepIds = new Set<string>();
        if (relationshipFilter === "all") {
            for (const n of live.nodes) keepIds.add(n.id);
        } else {
            for (const n of live.nodes) {
                if (n.data.focal) keepIds.add(n.id);
            }
            for (const e of edges) {
                keepIds.add(e.source);
                keepIds.add(e.target);
            }
        }

        const nodes = live.nodes
            .filter((n) => keepIds.has(n.id))
            .map((n): Node<SemanticNodeData> => {
                const isSelected = n.id === selectedId
                    || ((selection.kind === "concept" || selection.kind === "policy")
                        && n.data.conceptId === selection.conceptId)
                    || (selection.kind === "class" && n.data.qualifiedName === selection.qualifiedName);

                // Focal nodes (the ones the user explicitly opened) get a soft
                // amber halo so neighbours pulled in around them stay visually
                // secondary. The selected node gets a stronger blue ring on
                // top — both can apply at once.
                if (!isSelected && !n.data.focal) return n;
                const overlays: React.CSSProperties = {};
                if (n.data.focal && !isSelected) {
                    overlays.boxShadow = "0 0 0 2px rgba(217, 119, 6, 0.55)";
                }
                if (isSelected) {
                    overlays.boxShadow = "0 0 0 3px rgba(37, 99, 235, 0.55)";
                    overlays.borderColor = "#1e3a8a";
                }
                return {
                    ...n,
                    style: {
                        ...(n.style ?? {}),
                        ...overlays,
                    },
                };
            });

        const visibleNodeIds = new Set(nodes.map((n) => n.id));
        const finalEdges = edges.filter(
            (e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target),
        );
        return {nodes, edges: finalEdges};
    }, [live, relationshipFilter, selection]);

    const onNodeClick = useCallback<NodeMouseHandler<Node<SemanticNodeData>>>(
        (_evt, node) => {
            const data = node.data;
            if (data.kind === "class" || data.kind === "callsite") {
                dispatch(selectClass(data.qualifiedName ?? null));
            } else {
                dispatch(
                    selectConcept({
                        conceptId: data.conceptId ?? null,
                        isPolicy: data.kind === "policy",
                    }),
                );
            }
        },
        [dispatch],
    );

    const onFilterClick = useCallback(
        (id: RelationshipFilter) => () => {
            dispatch(setRelationshipFilter(id));
        },
        [dispatch],
    );

    // Re-fit the viewport whenever the visible-node set changes — fitView prop
    // alone only fires on mount, so switching filters or expanding the explored
    // pool would otherwise leave nodes parked off-screen.
    const flowRef = useRef<ReactFlowInstance<Node<SemanticNodeData>, Edge> | null>(null);
    const onInit = useCallback(
        (instance: ReactFlowInstance<Node<SemanticNodeData>, Edge>) => {
            flowRef.current = instance;
        },
        [],
    );
    useEffect(() => {
        const instance = flowRef.current;
        if (!instance) return;
        const handle = window.requestAnimationFrame(() => {
            instance.fitView({padding: 0.2, duration: 200});
        });
        return () => window.cancelAnimationFrame(handle);
    }, [visible.nodes.length, visible.edges.length, relationshipFilter]);

    const isLive = live !== DEMO;

    return (
        <div className="flex flex-col h-full">
            <div className="flex flex-row items-center justify-between gap-2 px-3 py-2 border-b border-slate-200 bg-slate-50">
                <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-slate-700">Graph</span>
                    {isLive ? (
                        <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">
                            live
                        </span>
                    ) : (
                        <span className="text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">
                            demo
                        </span>
                    )}
                    <span className="text-[10px] text-slate-500 ml-1">
                        {visible.nodes.length} / {live.nodes.length} nodes
                    </span>
                </div>
                <div className="flex flex-row gap-1" role="tablist" aria-label="Relationship filter">
                    {REL_FILTERS.map((f) => (
                        <button
                            key={f.id}
                            type="button"
                            role="tab"
                            title={f.hint}
                            aria-selected={relationshipFilter === f.id}
                            onClick={onFilterClick(f.id)}
                            className={[
                                "text-[10px] px-2 py-0.5 rounded-full border transition-colors",
                                relationshipFilter === f.id
                                    ? "bg-blue-100 border-blue-400 text-blue-800"
                                    : "bg-white border-slate-300 text-slate-600 hover:border-blue-300 hover:text-blue-600",
                            ].join(" ")}
                        >
                            {f.label}
                        </button>
                    ))}
                </div>
            </div>
            <SeedSearchBar/>
            <div className="flex-1 min-h-0">
                <ReactFlow
                    nodes={visible.nodes}
                    edges={visible.edges}
                    onNodeClick={onNodeClick}
                    onInit={onInit}
                    fitView
                    fitViewOptions={{padding: 0.2}}
                    proOptions={{hideAttribution: true}}
                    panOnScroll
                    zoomOnScroll
                    nodesDraggable={false}
                    nodesConnectable={false}
                >
                    <Background variant={BackgroundVariant.Dots} gap={16} size={1}/>
                    <Controls showInteractive={false}/>
                </ReactFlow>
            </div>
        </div>
    );
}

export default GraphPane;
