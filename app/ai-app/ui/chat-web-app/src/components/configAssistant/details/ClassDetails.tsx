import {useCallback, useMemo} from "react";
import {Crosshair, Eraser} from "lucide-react";

import AskAgentButton from "./AskAgentButton.tsx";
import {Section} from "./Section.tsx";
import {useFootprintLookup} from "../useCodeCoreLookup.ts";
import {useAppDispatch, useAppSelector} from "../../../app/store.ts";
import {
    ALL_FOOTPRINT_SLICES,
    FootprintSlice,
    forgetFootprint,
    recenterOn,
    selectConfigAssistantExpandedSlices,
    toggleFootprintSlice,
} from "../../../features/configAssistant/configAssistantSlice.ts";

interface Props {
    qualifiedName: string;
}

interface SemanticBadge {
    id?: string;
    name?: string;
    summary?: string;
}

const SLICE_LABEL: Record<FootprintSlice, string> = {
    ancestors: "Ancestors",
    descendants: "Descendants",
    callers: "Callers",
    callees: "Callees",
    concepts: "Concepts",
    policies: "Policies",
};

function ClassDetails({qualifiedName}: Props) {
    const lookup = useFootprintLookup(qualifiedName);
    const dispatch = useAppDispatch();
    const expandedSlices = useAppSelector(selectConfigAssistantExpandedSlices);
    const enabled = useMemo<Set<FootprintSlice>>(() => {
        const list = expandedSlices[qualifiedName];
        return new Set(list ?? ALL_FOOTPRINT_SLICES);
    }, [expandedSlices, qualifiedName]);

    const onToggleSlice = useCallback(
        (slice: FootprintSlice) => () => {
            dispatch(toggleFootprintSlice({qualifiedName, slice}));
        },
        [dispatch, qualifiedName],
    );
    const onRecenter = useCallback(() => {
        dispatch(recenterOn(qualifiedName));
    }, [dispatch, qualifiedName]);
    const onForget = useCallback(() => {
        dispatch(forgetFootprint(qualifiedName));
    }, [dispatch, qualifiedName]);

    const data = useMemo(() => {
        if (!lookup.data) return null;
        const fp = lookup.data.footprint?.[0];
        if (!fp) return null;
        return {
            footprint: fp,
            concepts: (lookup.data.concepts ?? []) as SemanticBadge[],
            style_policies: (lookup.data.style_policies ?? []) as SemanticBadge[],
        };
    }, [lookup.data]);

    const askPrompt = useMemo(
        () =>
            `Walk me through how to extend ${qualifiedName} for my own bundle. List which methods I'd typically override, which concepts it embodies, and which style policies I must follow.`,
        [qualifiedName],
    );

    if (!data) {
        const shortName = qualifiedName.split(".").slice(-1)[0] || qualifiedName;
        if (lookup.loading) {
            return (
                <div className="text-sm text-slate-700">
                    <p className="mb-1 font-medium">{shortName}</p>
                    <p className="text-[10px] font-mono text-slate-500 mb-2 break-all">{qualifiedName}</p>
                    <p className="text-xs text-slate-500 italic">Loading footprint…</p>
                </div>
            );
        }
        if (lookup.error) {
            return (
                <div className="text-sm text-slate-700">
                    <p className="mb-1 font-medium">{shortName}</p>
                    <p className="text-[10px] font-mono text-slate-500 mb-2 break-all">{qualifiedName}</p>
                    <p className="text-xs text-rose-600 mb-2">Lookup failed: {lookup.error}</p>
                    <AskAgentButton
                        label="Load class_footprint"
                        prompt={`Use code_graph.class_footprint on ${qualifiedName} and tell me what concepts it embodies and which style policies govern it.`}
                    />
                </div>
            );
        }
        return (
            <div className="text-sm text-slate-700">
                <p className="mb-1 font-medium">{shortName}</p>
                <p className="text-[10px] font-mono text-slate-500 mb-2 break-all">{qualifiedName}</p>
                <p className="text-xs text-slate-500">No footprint loaded yet.</p>
                <AskAgentButton
                    label="Load class_footprint"
                    prompt={`Use code_graph.class_footprint on ${qualifiedName} and tell me what concepts it embodies and which style policies govern it.`}
                />
            </div>
        );
    }

    const {footprint, concepts, style_policies} = data;
    const methodList = (footprint.methods ?? []).filter((m) => m && m.name);

    const sliceCounts: Record<FootprintSlice, number> = {
        ancestors: footprint.ancestors?.filter(Boolean).length ?? 0,
        descendants: footprint.descendants?.filter(Boolean).length ?? 0,
        callers: footprint.callers?.filter(Boolean).length ?? 0,
        callees: footprint.callees?.filter(Boolean).length ?? 0,
        concepts: concepts.length,
        policies: style_policies.length,
    };

    return (
        <div className="text-sm text-slate-800">
            <div className="mb-2 flex flex-row items-start justify-between gap-2">
                <div className="min-w-0">
                    <h3 className="text-base font-semibold">{footprint.name}</h3>
                    <p className="text-[10px] font-mono text-slate-500 break-all">
                        {footprint.qualified_name}
                    </p>
                </div>
                <div className="flex flex-row gap-1 flex-shrink-0">
                    <button
                        type="button"
                        onClick={onRecenter}
                        title="Re-center the graph on this class (drops other explored items)"
                        aria-label="Re-center on this class"
                        className="p-1 rounded hover:bg-blue-50 text-slate-500 hover:text-blue-600"
                    >
                        <Crosshair size={14}/>
                    </button>
                    <button
                        type="button"
                        onClick={onForget}
                        title="Forget this class (remove it from the graph)"
                        aria-label="Forget this class"
                        className="p-1 rounded hover:bg-rose-50 text-slate-500 hover:text-rose-600"
                    >
                        <Eraser size={14}/>
                    </button>
                </div>
            </div>

            {footprint.docstring && (
                <p className="text-xs italic text-slate-600 mb-3 leading-relaxed">
                    {footprint.docstring}
                </p>
            )}

            <Section title="Show in graph">
                <div className="flex flex-row flex-wrap gap-1">
                    {ALL_FOOTPRINT_SLICES.map((slice) => {
                        const count = sliceCounts[slice];
                        const isOn = enabled.has(slice);
                        const disabled = count === 0;
                        return (
                            <button
                                key={slice}
                                type="button"
                                onClick={onToggleSlice(slice)}
                                disabled={disabled}
                                title={
                                    disabled
                                        ? `${SLICE_LABEL[slice]} — none in this footprint`
                                        : isOn
                                            ? `Hide ${SLICE_LABEL[slice].toLowerCase()} from the graph`
                                            : `Show ${SLICE_LABEL[slice].toLowerCase()} in the graph`
                                }
                                className={[
                                    "text-[10px] px-1.5 py-0.5 rounded-full border transition-colors",
                                    disabled
                                        ? "bg-slate-50 border-slate-200 text-slate-400 cursor-not-allowed"
                                        : isOn
                                            ? "bg-blue-50 border-blue-300 text-blue-700"
                                            : "bg-white border-slate-300 text-slate-500 hover:border-blue-300",
                                ].join(" ")}
                            >
                                {SLICE_LABEL[slice]}{count > 0 ? ` ${count}` : ""}
                            </button>
                        );
                    })}
                </div>
            </Section>

            {!!concepts.length && (
                <Section title="Concepts">
                    <div className="flex flex-row flex-wrap gap-1">
                        {concepts.map((c) => (
                            <span
                                key={c.id}
                                className="text-[11px] px-1.5 py-0.5 rounded border border-amber-300 bg-amber-50 text-amber-800"
                                title={c.summary}
                            >
                                {c.name ?? c.id}
                            </span>
                        ))}
                    </div>
                </Section>
            )}

            {!!style_policies.length && (
                <Section title="Style policies">
                    <div className="flex flex-row flex-wrap gap-1">
                        {style_policies.map((p) => (
                            <span
                                key={p.id}
                                className="text-[11px] px-1.5 py-0.5 rounded border border-violet-300 bg-violet-50 text-violet-800"
                                title={p.summary}
                            >
                                {p.name ?? p.id}
                            </span>
                        ))}
                    </div>
                </Section>
            )}

            {!!footprint.ancestors?.filter(Boolean).length && (
                <Section title="Inherits">
                    <ul className="space-y-0.5 break-all">
                        {footprint.ancestors.filter(Boolean).map((q) => (
                            <li key={q} className="font-mono text-[11px]">{q}</li>
                        ))}
                    </ul>
                </Section>
            )}

            {!!methodList.length && (
                <Section title={`Methods (${methodList.length})`}>
                    <ul className="space-y-0.5">
                        {methodList.slice(0, 12).map((m, i) => (
                            <li key={`${m.name}-${i}`} className="font-mono text-[11px]">
                                {m.is_abstract && <span className="text-rose-600 mr-1">abstract</span>}
                                <span className="text-slate-900">{m.name}</span>
                                {m.signature && <span className="text-slate-500">{m.signature}</span>}
                            </li>
                        ))}
                        {methodList.length > 12 && (
                            <li className="text-[11px] text-slate-500 italic">
                                … {methodList.length - 12} more
                            </li>
                        )}
                    </ul>
                </Section>
            )}

            {!!footprint.descendants?.filter(Boolean).length && (
                <Section title={`Inherited by (${footprint.descendants.filter(Boolean).length})`}>
                    <ul className="space-y-0.5 break-all">
                        {footprint.descendants.filter(Boolean).slice(0, 6).map((q) => (
                            <li key={q} className="font-mono text-[11px]">{q}</li>
                        ))}
                    </ul>
                </Section>
            )}

            {!!footprint.callers?.filter(Boolean).length && (
                <Section title={`Used by (${footprint.callers.filter(Boolean).length})`}>
                    <ul className="space-y-0.5 break-all">
                        {footprint.callers.filter(Boolean).slice(0, 6).map((q) => (
                            <li key={q} className="font-mono text-[11px]">{q}</li>
                        ))}
                    </ul>
                </Section>
            )}

            {!!footprint.callees?.filter(Boolean).length && (
                <Section title={`Calls (${footprint.callees.filter(Boolean).length})`}>
                    <ul className="space-y-0.5 break-all">
                        {footprint.callees.filter(Boolean).slice(0, 6).map((q) => (
                            <li key={q} className="font-mono text-[11px]">{q}</li>
                        ))}
                    </ul>
                </Section>
            )}

            <AskAgentButton label="How do I extend this →" prompt={askPrompt}/>
            {!lookup.fromArtifact && (
                <div className="text-[10px] text-slate-400 mt-2 italic">
                    Loaded directly from the code-graph.
                </div>
            )}
        </div>
    );
}

export default ClassDetails;
