import {useMemo} from "react";

import {useAppSelector} from "../../app/store.ts";
import {selectCurrentTurn} from "../../features/chat/chatStateSlice.ts";
import {CODE_CORE_ARTIFACT_TYPE, CodeCoreArtifact} from "../../features/logExtensions/codeCore/types.ts";

/**
 * Returns the most recent CodeCoreArtifact for the given kinds in the
 * current turn, or null if none yet. Used by inspect-panel tabs to render
 * tool-call results without subscribing to the raw stream.
 */
export function useCodeCoreArtifact(kinds: ReadonlyArray<string>): CodeCoreArtifact | null {
    const currentTurn = useAppSelector(selectCurrentTurn);
    return useMemo(() => {
        if (!currentTurn) return null;
        const filtered = currentTurn.artifacts.filter(
            (a) => a.artifactType === CODE_CORE_ARTIFACT_TYPE,
        ) as CodeCoreArtifact[];
        const matching = filtered.filter((a) => kinds.includes(a.content.kind));
        if (!matching.length) return null;
        // Latest by timestamp.
        return matching.reduce((latest, cur) =>
            (cur.content.timestamp > latest.content.timestamp ? cur : latest),
        );
    }, [currentTurn, kinds]);
}
