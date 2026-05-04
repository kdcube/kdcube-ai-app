import {createSlice, PayloadAction} from "@reduxjs/toolkit";
import {RootState} from "../../app/store.ts";

/**
 * Filter chip in the graph header. Maps to edge `relKind` values produced
 * by buildGraph.ts:
 *   inheritance -> INHERITS / INHERITED_BY
 *   calls       -> CALLS / CALLED_BY
 *   semantic    -> EMBODIES / GOVERNED_BY / RELATED_TO / REALIZED_BY
 *   all         -> show everything
 */
export type RelationshipFilter = "all" | "inheritance" | "calls" | "semantic";

/**
 * Slices a class footprint can render into the graph. The user toggles
 * these per focal class to keep the canvas under control.
 */
export type FootprintSlice =
    | "ancestors"
    | "descendants"
    | "callers"
    | "callees"
    | "concepts"
    | "policies";

export const ALL_FOOTPRINT_SLICES: FootprintSlice[] = [
    "ancestors",
    "descendants",
    "callers",
    "callees",
    "concepts",
    "policies",
];

/**
 * Cross-type cap on the explored pool. Each entry contributes ≈ 4–6 nodes
 * to the graph after the build-time per-category limits, so 8 entries land
 * us in the 30–40 node target zone.
 */
const EXPLORED_MAX_ENTRIES = 8;

export interface ConfigAssistantSelection {
    /**
     * "class" — a Class node was clicked; qualifiedName is set.
     * "concept" — a Semantic node (kind=concept|term) was clicked; conceptId is set.
     * "policy" — a Semantic node (kind=policy) was clicked; conceptId is set.
     * null — nothing selected, DetailsPane shows the empty hint.
     */
    kind: "class" | "concept" | "policy" | null;
    qualifiedName: string | null;
    conceptId: string | null;
}

/**
 * Pool of code-graph data the UI has fetched directly (not via the agent).
 * Populated as the user clicks graph nodes and useCodeCoreLookup hooks
 * resolve. Merged into the graph alongside the agent's artifacts so the
 * graph grows as the user explores.
 */
export interface ExploredPool {
    /** conceptId -> serialised /define response (kept generic to avoid a circular import) */
    defines: Record<string, unknown>;
    /** qualified_name -> serialised /class_footprint response */
    footprints: Record<string, unknown>;
    /**
     * Insertion-order log so cross-type pruning can drop the genuinely
     * oldest entry. Each token is `d:<conceptId>` or `f:<qualifiedName>`.
     */
    order: string[];
}

export interface ConfigAssistantState {
    mode: string | null;
    drawerOpen: boolean;
    /** When true the drawer expands to ~90vw so the graph has real room. */
    drawerMaximized: boolean;
    /**
     * Sticky bit: once the user closes the drawer in this turn/conversation
     * we don't auto-reopen on subsequent code_core artifacts. Cleared on
     * conversation change or by an explicit openDrawer().
     */
    userClosed: boolean;
    selection: ConfigAssistantSelection;
    relationshipFilter: RelationshipFilter;
    explored: ExploredPool;
    /**
     * Per-focal-class toggle: which footprint slices render into the graph.
     * Defaults to all six slices when a footprint first lands. Users tighten
     * this from the drawer to keep the canvas readable.
     */
    expandedSlices: Record<string, FootprintSlice[]>;
}

const initialState: ConfigAssistantState = {
    mode: null,
    drawerOpen: false,
    drawerMaximized: false,
    userClosed: false,
    selection: {kind: null, qualifiedName: null, conceptId: null},
    relationshipFilter: "all",
    explored: {defines: {}, footprints: {}, order: []},
    expandedSlices: {},
};

const touchOrder = (pool: ExploredPool, token: string): void => {
    const existing = pool.order.indexOf(token);
    if (existing >= 0) pool.order.splice(existing, 1);
    pool.order.push(token);
};

const pruneExplored = (
    pool: ExploredPool,
    maxEntries: number,
    expandedSlices: Record<string, FootprintSlice[]>,
): void => {
    while (pool.order.length > maxEntries) {
        const oldest = pool.order.shift();
        if (!oldest) break;
        const [type, ...rest] = oldest.split(":");
        const key = rest.join(":");
        if (type === "d") delete pool.defines[key];
        else if (type === "f") {
            delete pool.footprints[key];
            delete expandedSlices[key];
        }
    }
};

const configAssistantSlice = createSlice({
    name: "configAssistant",
    initialState,
    reducers: {
        setMode(state, action: PayloadAction<string | null>) {
            state.mode = action.payload;
            // Turning the mode off implicitly closes the drawer.
            if (action.payload === null) {
                state.drawerOpen = false;
                state.userClosed = false;
            }
        },
        openDrawer(state) {
            state.drawerOpen = true;
            state.userClosed = false;
        },
        closeDrawer(state) {
            state.drawerOpen = false;
            state.userClosed = true;
        },
        toggleDrawer(state) {
            if (state.drawerOpen) {
                state.drawerOpen = false;
                state.userClosed = true;
            } else {
                state.drawerOpen = true;
                state.userClosed = false;
            }
        },
        toggleDrawerMaximized(state) {
            state.drawerMaximized = !state.drawerMaximized;
        },
        /** Auto-open trigger from artifact arrival; respects the userClosed bit. */
        ensureDrawerOpen(state) {
            if (!state.userClosed) state.drawerOpen = true;
        },
        /** Reset on conversation change so a new conversation starts fresh. */
        resetDrawerStickiness(state) {
            state.userClosed = false;
            state.drawerOpen = false;
            state.explored = {defines: {}, footprints: {}, order: []};
            state.expandedSlices = {};
        },
        rememberDefine(state, action: PayloadAction<{conceptId: string; data: unknown}>) {
            const key = action.payload.conceptId.toLowerCase();
            state.explored.defines[key] = action.payload.data;
            touchOrder(state.explored, `d:${key}`);
            pruneExplored(state.explored, EXPLORED_MAX_ENTRIES, state.expandedSlices);
        },
        rememberFootprint(state, action: PayloadAction<{qualifiedName: string; data: unknown}>) {
            const key = action.payload.qualifiedName;
            state.explored.footprints[key] = action.payload.data;
            touchOrder(state.explored, `f:${key}`);
            // First time we see this focal — default to all slices on. Re-clicks
            // preserve whatever the user already toggled off.
            if (!state.expandedSlices[key]) {
                state.expandedSlices[key] = [...ALL_FOOTPRINT_SLICES];
            }
            pruneExplored(state.explored, EXPLORED_MAX_ENTRIES, state.expandedSlices);
        },
        toggleFootprintSlice(
            state,
            action: PayloadAction<{qualifiedName: string; slice: FootprintSlice}>,
        ) {
            const {qualifiedName, slice} = action.payload;
            const current = state.expandedSlices[qualifiedName] ?? [...ALL_FOOTPRINT_SLICES];
            const next = current.includes(slice)
                ? current.filter((s) => s !== slice)
                : [...current, slice];
            state.expandedSlices[qualifiedName] = next;
        },
        /**
         * Drop everything in the explored pool except the focal class —
         * useful when the canvas gets crowded and the user wants to start
         * a fresh exploration around one node.
         */
        recenterOn(state, action: PayloadAction<string>) {
            const qn = action.payload;
            const fp = state.explored.footprints[qn];
            state.explored = {
                defines: {},
                footprints: fp ? {[qn]: fp} : {},
                order: fp ? [`f:${qn}`] : [],
            };
            const slices = state.expandedSlices[qn];
            state.expandedSlices = slices ? {[qn]: slices} : {};
            state.selection = {kind: fp ? "class" : null, qualifiedName: fp ? qn : null, conceptId: null};
        },
        /**
         * Remove a single focal class from the pool. The graph keeps the
         * other explored entries; selection clears.
         */
        forgetFootprint(state, action: PayloadAction<string>) {
            const qn = action.payload;
            delete state.explored.footprints[qn];
            delete state.expandedSlices[qn];
            state.explored.order = state.explored.order.filter((t) => t !== `f:${qn}`);
            if (state.selection.qualifiedName === qn) {
                state.selection = {kind: null, qualifiedName: null, conceptId: null};
            }
        },
        clearExplored(state) {
            state.explored = {defines: {}, footprints: {}, order: []};
            state.expandedSlices = {};
        },
        selectClass(state, action: PayloadAction<string | null>) {
            const qn = action.payload;
            state.selection = {
                kind: qn ? "class" : null,
                qualifiedName: qn,
                conceptId: null,
            };
        },
        selectConcept(
            state,
            action: PayloadAction<{conceptId: string | null; isPolicy?: boolean}>,
        ) {
            const {conceptId, isPolicy} = action.payload;
            state.selection = {
                kind: conceptId ? (isPolicy ? "policy" : "concept") : null,
                qualifiedName: null,
                conceptId,
            };
        },
        clearSelection(state) {
            state.selection = {kind: null, qualifiedName: null, conceptId: null};
        },
        setRelationshipFilter(state, action: PayloadAction<RelationshipFilter>) {
            state.relationshipFilter = action.payload;
        },
        resetConfigAssistant() {
            return initialState;
        },
    },
});

export const {
    setMode,
    openDrawer,
    closeDrawer,
    toggleDrawer,
    toggleDrawerMaximized,
    ensureDrawerOpen,
    resetDrawerStickiness,
    rememberDefine,
    rememberFootprint,
    toggleFootprintSlice,
    recenterOn,
    forgetFootprint,
    clearExplored,
    selectClass,
    selectConcept,
    clearSelection,
    setRelationshipFilter,
    resetConfigAssistant,
} = configAssistantSlice.actions;

export const selectConfigAssistantMode = (state: RootState) => state.configAssistant.mode;
export const selectConfigAssistantDrawerOpen = (state: RootState) => state.configAssistant.drawerOpen;
export const selectConfigAssistantDrawerMaximized = (state: RootState) => state.configAssistant.drawerMaximized;
export const selectConfigAssistantSelection = (state: RootState) => state.configAssistant.selection;
export const selectConfigAssistantRelationshipFilter = (state: RootState) =>
    state.configAssistant.relationshipFilter;
export const selectConfigAssistantExplored = (state: RootState) => state.configAssistant.explored;
export const selectConfigAssistantExpandedSlices = (state: RootState) =>
    state.configAssistant.expandedSlices;

export default configAssistantSlice.reducer;
