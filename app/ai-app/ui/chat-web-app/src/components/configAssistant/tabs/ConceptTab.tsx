/*
 * ConceptTab — renders the canonical definition of a framework concept or
 * style policy, sourced from the latest `code_core.define` artifact in the
 * current turn.
 */
import {useMemo} from "react";

import {TabEmpty, TabFrame} from "./TabFrame.tsx";
import {useCodeCoreArtifact} from "../useCodeCoreArtifact.ts";

const KINDS = ["define"] as const;

interface SemanticMatch {
    id?: string;
    kind?: string;
    scope?: string;
    name?: string;
    aliases?: string[];
    category?: string;
    summary?: string;
    definition?: string;
    rationale?: string;
    how_to_apply?: string;
    pitfalls?: string[];
    related?: Array<{id?: string; name?: string; kind?: string; scope?: string}>;
    realized_by?: string[];
    applied_to?: string[];
}

function ConceptTab() {
    const artifact = useCodeCoreArtifact(KINDS);

    const match = useMemo<SemanticMatch | null>(() => {
        if (!artifact) return null;
        const payload = artifact.content.payload as {matches?: SemanticMatch[]; error?: string} | null;
        if (!payload?.matches?.length) return null;
        return payload.matches[0];
    }, [artifact]);

    if (!match) {
        return (
            <TabFrame title="Concept" subtitle="Framework definitions">
                <TabEmpty>
                    Ask <em>“what is a Bundle?”</em> in the chat. As soon as the
                    assistant calls{" "}
                    <code className="mx-1 px-1 py-0.5 bg-slate-100 rounded">code_graph.define</code>,
                    the canonical definition and links will appear here.
                </TabEmpty>
            </TabFrame>
        );
    }

    const isPolicy = match.kind === "policy";

    return (
        <TabFrame
            title={match.name ?? match.id ?? "Concept"}
            subtitle={`${match.kind ?? "concept"} · ${match.scope ?? "framework"}${match.category ? ` · ${match.category}` : ""}`}
        >
            {!!match.aliases?.length && (
                <div className="mb-2 flex flex-row flex-wrap gap-1">
                    {match.aliases.map((a) => (
                        <span key={a} className="text-[10px] px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">
                            alias: {a}
                        </span>
                    ))}
                </div>
            )}
            {match.summary && (
                <p className="text-sm text-slate-700 mb-3 leading-relaxed">{match.summary}</p>
            )}
            {match.definition && match.definition !== match.summary && (
                <details className="mb-3" open>
                    <summary className="text-xs font-medium text-slate-500 cursor-pointer mb-1">
                        Full definition
                    </summary>
                    <pre className="text-xs whitespace-pre-wrap text-slate-700 bg-slate-50 p-2 rounded border border-slate-200">
                        {match.definition}
                    </pre>
                </details>
            )}
            {isPolicy && match.rationale && (
                <Section title="Rationale">{match.rationale}</Section>
            )}
            {isPolicy && match.how_to_apply && (
                <Section title="How to apply">{match.how_to_apply}</Section>
            )}
            {!!match.pitfalls?.length && (
                <Section title="Pitfalls">
                    <ul className="list-disc pl-5 space-y-0.5">
                        {match.pitfalls.map((p, i) => (
                            <li key={i}>{p}</li>
                        ))}
                    </ul>
                </Section>
            )}
            {!!match.related?.length && (
                <Section title="Related">
                    <div className="flex flex-row flex-wrap gap-1">
                        {match.related.map((r) => (
                            <span
                                key={`${r.scope ?? "?"}-${r.id}`}
                                className="text-[11px] px-1.5 py-0.5 rounded border border-amber-300 bg-amber-50 text-amber-800"
                                title={`${r.kind ?? ""}`}
                            >
                                {r.name ?? r.id}
                            </span>
                        ))}
                    </div>
                </Section>
            )}
            {!!match.realized_by?.length && (
                <Section title="Realized by (code)">
                    <ul className="list-disc pl-5 space-y-0.5 break-all">
                        {match.realized_by.map((q) => (
                            <li key={q} className="font-mono text-[11px]">{q}</li>
                        ))}
                    </ul>
                </Section>
            )}
            {!!match.applied_to?.length && (
                <Section title="Applied to (governed code)">
                    <ul className="list-disc pl-5 space-y-0.5 break-all">
                        {match.applied_to.map((q) => (
                            <li key={q} className="font-mono text-[11px]">{q}</li>
                        ))}
                    </ul>
                </Section>
            )}
        </TabFrame>
    );
}

function Section({title, children}: {title: string; children: React.ReactNode}) {
    return (
        <div className="mb-3">
            <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide mb-1">
                {title}
            </div>
            <div className="text-xs text-slate-700 leading-relaxed">{children}</div>
        </div>
    );
}

export default ConceptTab;
