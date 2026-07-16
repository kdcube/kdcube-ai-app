---
id: kdcube-ai-app/app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/ported-langgraph-agents@2026-07-13/docs/journal/journal.md
title: "Ported LangGraph Agents Build Journal"
summary: "Stable chronological index for the ported-langgraph-agents@2026-07-13 package journal."
status: active
tags: ["ported-langgraph-agents", "journal", "multi-agent", "package"]
---

# Ported LangGraph Agents Build Journal

Stable chronological index of the bundle-local package journal. New entries live as
dated files in this directory.

| Date | Entry | Summary |
| --- | --- | --- |
| 2026-07-13 | [Consolidate two ported agents into one multi-agent app](2026-07-13-consolidate-two-ported-agents.md) | Historical consolidation record. Its original graph-cache, `create_react_agent`, and per-agent-schema details are superseded; current behavior is per-turn graph rebuild, `langchain.agents.create_agent`, and one tenant/project schema with `agent_id` row/key scope. |
| 2026-07-16 | [Platform web tools, output budget as a descriptor property, tool-call visibility](2026-07-16-web-tools-output-budget-steps.md) | lg-react gains `web_search`/`web_fetch` (one `web` connection; dual accountable providers — search backend + llm filter/segment on the accounted model service). Answer-model output budgets become descriptor properties (`agents.<id>.model.max_tokens`: 16384 react / 8192 solution) after a live truncation loop (tool call cut mid-arguments at the adapter's 1200 default → recursion limit); the SDK bridge now explains a full-budget interruption to the model in-band and to the log with evidence. Steps show per-invocation tool-call signatures + arguments; empty args stated. Descriptors synced across demo-project, custom-authority, ecs-demo, ecs-cloudcost, and the default-install referent. |

## Baseline carried forward

Both agents' runtime integrations were already in place and verified before this
journal opened: the research graph's dedicated-answer-node stream adapter + async
storage edge + economics, and the create_react agent's looping-agent-node adapter +
tools seam. This journal starts at the consolidation into the multi-agent package.
