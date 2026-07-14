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
| 2026-07-13 | [Consolidate two ported agents into one multi-agent app](2026-07-13-consolidate-two-ported-agents.md) | Merged the two single-agent port bundles (a research graph and the prebuilt create_react_agent) into ONE app that hosts BOTH, dispatched by `agent_id` through a single `execute_core`. Per-agent graph cache + stream adapter + storage schema; the identity gate folds `agent_id` into the per-user key. The two source bundles were retired; both POCs are untouched. |

## Baseline carried forward

Both agents' runtime integrations were already in place and verified before this
journal opened: the research graph's dedicated-answer-node stream adapter + async
storage edge + economics, and the create_react agent's looping-agent-node adapter +
tools seam. This journal starts at the consolidation into the multi-agent package.
