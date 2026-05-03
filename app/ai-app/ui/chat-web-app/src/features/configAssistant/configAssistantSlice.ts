import {createSlice, PayloadAction} from "@reduxjs/toolkit";
import {RootState} from "../../app/store.ts";

export type ScopeFilter = "all" | "framework" | "my_bundle";

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
    scope: {
        packageFilter: string;
        scopeFilter: ScopeFilter;
    };
    explored: ExploredPool;
}

const initialState: ConfigAssistantState = {
    mode: null,
    drawerOpen: false,
    drawerMaximized: false,
    userClosed: false,
    selection: {kind: null, qualifiedName: null, conceptId: null},
    scope: {packageFilter: "", scopeFilter: "all"},
    explored: {defines: {}, footprints: {}},
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
            state.explored = {defines: {}, footprints: {}};
        },
        rememberDefine(state, action: PayloadAction<{conceptId: string; data: unknown}>) {
            const key = action.payload.conceptId.toLowerCase();
            state.explored.defines[key] = action.payload.data;
        },
        rememberFootprint(state, action: PayloadAction<{qualifiedName: string; data: unknown}>) {
            state.explored.footprints[action.payload.qualifiedName] = action.payload.data;
        },
        clearExplored(state) {
            state.explored = {defines: {}, footprints: {}};
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
        setPackageFilter(state, action: PayloadAction<string>) {
            state.scope.packageFilter = action.payload;
        },
        setScopeFilter(state, action: PayloadAction<ScopeFilter>) {
            state.scope.scopeFilter = action.payload;
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
    clearExplored,
    selectClass,
    selectConcept,
    clearSelection,
    setPackageFilter,
    setScopeFilter,
    resetConfigAssistant,
} = configAssistantSlice.actions;

export const selectConfigAssistantMode = (state: RootState) => state.configAssistant.mode;
export const selectConfigAssistantDrawerOpen = (state: RootState) => state.configAssistant.drawerOpen;
export const selectConfigAssistantDrawerMaximized = (state: RootState) => state.configAssistant.drawerMaximized;
export const selectConfigAssistantSelection = (state: RootState) => state.configAssistant.selection;
export const selectConfigAssistantScope = (state: RootState) => state.configAssistant.scope;
export const selectConfigAssistantExplored = (state: RootState) => state.configAssistant.explored;

export default configAssistantSlice.reducer;
