/*
 * FootprintTab — structural class card sourced from the latest
 * code_core.class_footprint artifact, with concepts + style policies that
 * the augmented backend tool now returns alongside the structural data.
 */
import {useMemo} from "react";

import {TabEmpty, TabFrame} from "./TabFrame.tsx";
import {useCodeCoreArtifact} from "../useCodeCoreArtifact.ts";

const KINDS = ["class_footprint"] as const;

interface FootprintRecord {
    name?: string;
    qualified_name?: string;
    docstring?: string;
    file_path?: string;
    ancestors?: string[];
    descendants?: string[];
    methods?: Array<{name?: string; signature?: string; docstring?: string; is_abstract?: boolean}>;
    properties?: string[];
    callers?: string[];
    callees?: string[];
    docs?: Array<{title?: string; path?: string}>;
    tests?: string[];
    decorators?: string[];
}

interface SemanticBadge {
    id?: string;
    name?: string;
    summary?: string;
    category?: string;
}

interface FootprintPayload {
    footprint?: FootprintRecord[];
    concepts?: SemanticBadge[];
    style_policies?: SemanticBadge[];
    error?: string;
}

function FootprintTab() {
    const artifact = useCodeCoreArtifact(KINDS);

    const data = useMemo(() => {
        if (!artifact) return null;
        const payload = artifact.content.payload as FootprintPayload | null;
        if (!payload || payload.error) return null;
        const footprint = payload.footprint?.[0] ?? null;
        if (!footprint) return null;
        return {
            footprint,
            concepts: payload.concepts ?? [],
            style_policies: payload.style_policies ?? [],
        };
    }, [artifact]);

    if (!data) {
        return (
            <TabFrame title="Footprint" subtitle="Structural class card">
                <TabEmpty>
                    Ask the assistant about a class — e.g.{" "}
                    <em>“class_footprint of KBClient”</em>. The methods, callers,
                    embodied concepts, and governing style policies will land
                    here.
                </TabEmpty>
            </TabFrame>
        );
    }

    const {footprint, concepts, style_policies} = data;
    const methodList = (footprint.methods ?? []).filter((m) => m && m.name);

    return (
        <TabFrame
            title={footprint.name ?? "Class"}
            subtitle={footprint.qualified_name}
            actions={
                footprint.file_path && (
                    <span className="text-[10px] font-mono text-slate-500 truncate max-w-[180px]" title={footprint.file_path}>
                        {footprint.file_path}
                    </span>
                )
            }
        >
            {footprint.docstring && (
                <p className="text-xs text-slate-600 italic mb-3 leading-relaxed">{footprint.docstring}</p>
            )}

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

            {!!footprint.ancestors?.length && (
                <Section title="Ancestors">
                    <ul className="list-disc pl-5 space-y-0.5 break-all">
                        {footprint.ancestors.filter(Boolean).map((q) => (
                            <li key={q} className="font-mono text-[11px]">{q}</li>
                        ))}
                    </ul>
                </Section>
            )}

            {!!methodList.length && (
                <Section title={`Methods (${methodList.length})`}>
                    <ul className="space-y-1">
                        {methodList.slice(0, 25).map((m, i) => (
                            <li key={`${m.name}-${i}`} className="font-mono text-[11px]">
                                {m.is_abstract && <span className="text-rose-600 mr-1">abstract</span>}
                                <span className="text-slate-900">{m.name}</span>
                                {m.signature && <span className="text-slate-500">{m.signature}</span>}
                            </li>
                        ))}
                        {methodList.length > 25 && (
                            <li className="text-[11px] text-slate-500 italic">
                                … {methodList.length - 25} more
                            </li>
                        )}
                    </ul>
                </Section>
            )}

            {!!footprint.callers?.filter(Boolean).length && (
                <Section title={`Callers (${footprint.callers.filter(Boolean).length})`}>
                    <ul className="list-disc pl-5 space-y-0.5 break-all">
                        {footprint.callers.filter(Boolean).slice(0, 15).map((q) => (
                            <li key={q} className="font-mono text-[11px]">{q}</li>
                        ))}
                    </ul>
                </Section>
            )}

            {!!footprint.tests?.filter(Boolean).length && (
                <Section title={`Tests (${footprint.tests.filter(Boolean).length})`}>
                    <ul className="list-disc pl-5 space-y-0.5 break-all">
                        {footprint.tests.filter(Boolean).slice(0, 10).map((q) => (
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
            {children}
        </div>
    );
}

export default FootprintTab;
