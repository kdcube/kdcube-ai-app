import {ArtifactStreamDataItem, ArtifactStreamParser} from "../../conversations/conversationsTypes.ts";
import {UnknownArtifact} from "../../chat/chatTypes.ts";
import {CODE_CORE_ARTIFACT_TYPE, CodeCoreArtifact, subTypeToKind} from "./types.ts";

/**
 * Collects subsystem events with `sub_type=code_core.<kind>` (one per
 * successful code_graph.* tool result, emitted only in config_assistant
 * mode). Each unique tool_call_id becomes one CodeCoreArtifact.
 */
export class CodeCoreArtifactStreamReducer implements ArtifactStreamParser {
    private artifacts: CodeCoreArtifact[] = [];

    process(data: ArtifactStreamDataItem): boolean {
        if (data.marker !== "subsystem") return false;
        const subType = (data.extra?.sub_type as string | undefined) ?? undefined;
        const kind = subTypeToKind(subType);
        if (!kind) return false;

        const callId = (data.extra?.execution_id as string | undefined) ?? data.artifact_name ?? `${kind}-${data.ts_first}`;
        const text = data.text ?? "";

        let payload: unknown = null;
        if (text) {
            try {
                payload = JSON.parse(text);
            } catch {
                // Ignore — backend always JSON-encodes, but be defensive.
                payload = text;
            }
        }

        const idx = this.artifacts.findIndex((a) => a.content.callId === callId);
        const next: CodeCoreArtifact = {
            artifactType: CODE_CORE_ARTIFACT_TYPE,
            timestamp: data.ts_first,
            content: {kind, callId, payload, timestamp: data.ts_first},
        };
        if (idx >= 0) {
            this.artifacts.splice(idx, 1, next);
        } else {
            this.artifacts.push(next);
        }
        return true;
    }

    flush(): UnknownArtifact[] {
        const r = this.artifacts;
        this.artifacts = [];
        return r;
    }
}
