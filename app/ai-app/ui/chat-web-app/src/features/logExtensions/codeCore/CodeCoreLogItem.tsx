import {useMemo} from "react";
import {Sparkles} from "lucide-react";

import {ChatLogComponentProps} from "../../extensions/logExtesnions.ts";
import {CODE_CORE_ARTIFACT_TYPE, CodeCoreArtifact} from "./types.ts";

/**
 * Small inline marker rendered in the chat log when a code_graph.* tool
 * succeeds in config_assistant mode. The actual rich render lives in the
 * inspect panel (Concept / Footprint tabs); this is just a breadcrumb.
 */
function CodeCoreLogItem({item}: ChatLogComponentProps) {
    if (item.artifactType !== CODE_CORE_ARTIFACT_TYPE) {
        throw new Error("not a CodeCoreArtifact");
    }
    const artifact = item as CodeCoreArtifact;
    const kind = artifact.content.kind;

    return useMemo(() => {
        return (
            <div className="my-1 flex flex-row items-center gap-2 px-2 py-1 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded">
                <Sparkles size={12} className="text-amber-500"/>
                <span>
                    code_core.<code className="font-mono">{kind}</code> available — see the inspect panel.
                </span>
            </div>
        );
    }, [kind]);
}

export default CodeCoreLogItem;
