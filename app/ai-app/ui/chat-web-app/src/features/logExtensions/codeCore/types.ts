import {Artifact} from "../../chat/chatTypes.ts";

/**
 * Backend emits one subsystem event per successful code_graph.* tool call
 * when mode=config_assistant. sub_type is `code_core.<kind>` where kind is
 * the suffix of the kernel function name (define, class_footprint, etc.).
 */

export type CodeCoreKind =
    | "define"
    | "class_footprint"
    | "code_search"
    | "find_references"
    | "find_siblings"
    | "trace_call_chain"
    | "find_docs_for_code"
    | "show_architecture"
    | "show_contract"
    | "impact_analysis";

export const CODE_CORE_ARTIFACT_TYPE = "code_core" as const;

export interface CodeCoreArtifactData {
    /** code_graph.<kind> sub-string (e.g. "define"). */
    kind: CodeCoreKind | string;
    /** tool_call_id used to dedupe. */
    callId: string;
    /** Parsed JSON payload from the tool. Shape depends on kind. */
    payload: unknown;
    /** Original timestamp of the first event for this call. */
    timestamp: number;
}

export interface CodeCoreArtifact extends Artifact<CodeCoreArtifactData> {
    artifactType: typeof CODE_CORE_ARTIFACT_TYPE;
}

export const subTypeToKind = (subType: string | undefined): string | null => {
    if (!subType) return null;
    if (!subType.startsWith("code_core.")) return null;
    return subType.slice("code_core.".length);
};
