---
id: ported-langgraph-agents@2026-07-13/docs/journal/2026-07-16-web-tools-output-budget-steps
title: "2026-07-16 — Platform web tools, output budget as a descriptor property, tool-call visibility"
status: active
tags: ["ported-langgraph-agents", "journal", "web-tools", "accounting", "max-tokens", "steps", "descriptor-config"]
---

# 2026-07-16 — Platform web tools, output budget as a descriptor property, tool-call visibility

Context: this lands after the 2026-07-15/16 turn-workspace wave (turn-batch fold in
`platform/turn_batch.py`; the read/pull/exec triad + in-band turn frame in
`platform/turn_workspace.py` — see the port recipe's "distributed turn workspace"
section for the paradigm).

## Web tools connected (lg-react)

`platform/web_tools.py` binds the platform's paid web backends as plain LangChain
tools, declared as ONE connection in the agent's tool list:

```yaml
- name: web
  kind: python
  alias: web
  allowed: [web_search, web_fetch]
```

Two accountable providers meter per call, both through seams the port already
stands on: the **web_search provider** (per-deployment backend, e.g. Brave; key
from platform secrets `services.brave.api_key`) meters inside the backend against
the ambient turn accounting context; the **llm provider** (result
reconciliation + filtering/segmentation) runs on the entrypoint's accounted
`models_service`, passed into the tool factories. Result rows are shaped for a
chat model: accounting-only (`provider`) and binary (`base64`) fields dropped
(mime + size stay), page content bounded per row and per call, truncation stated
in-band. `tool_pick.select_bound_tools` gained a generic `extra_factories` slot
for such runtime-wired tools; the picker ceiling/deny-map semantics are
unchanged. Verified live: a searching turn shows the results widget and the turn
breakdown carries BOTH meters.

## Output budget: a descriptor property (the truncation-loop fix)

First live payload-bearing exec ask ("make an HTML page from those news") looped
to `GraphRecursionError(25)`: the LangChain adapter's default `max_tokens` (1200)
cut every response MID-TOOL-CALL (`run_python(code=<full HTML page>)`), the
truncated args failed tool validation, and the model retried into the same
ceiling — accounting showed 12 calls at exactly 1200 output tokens.

The budget is now a **descriptor property** (KDCube apps are configured through
the descriptor, never process env vars; the vendored configs' env knobs are
standalone-only fallbacks):

```yaml
surfaces.as_consumer.agents.lg-react.model.max_tokens: 16384   # payload tool calls
surfaces.as_consumer.agents.lg-solution.model.max_tokens: 8192 # prose answers
```

`entrypoint._agent_max_tokens` overlays the property onto the vendored config for
both agents. Size the budget as a generous safety cap that fits narration + ONE
complete payload-bearing tool call; the model stops on its own. The SDK LangChain
bridge (`frameworks/langchain/chat_model.py`) additionally EXPLAINS a full-budget
spend to both audiences: an in-band notice in the assistant's own interrupted
message (so the next round the model acts on "I was cut off" instead of
confabulating around "missing argument") and an `INTERRUPTED` log with evidence
(each reconstructed call's name, args size, cut tail).

## Steps show how tools were called

`platform/stream_prebuilt.py` now emits each tool INVOCATION as its own step
(`run_python`, `run_python (2)`, …): title = compact call signature
(`run_python(code=<2.4 KB>, prog_name='news')`), body = the arguments (large
strings as fenced blocks, truncated with total stated). A call arriving with no
usable arguments renders as `run_python()` + "No arguments received." — the
truncation incident above would have been visible in the Steps tab at a glance.

## Config alignment

The `web` connection + both `model.max_tokens` properties are declared in
`config/bundles.template.yaml` (web OFF by default, documented) and synced across
the deployed descriptors: demo-tenant demo-project + custom-authority (local
runtime), ecs-demo + ecs-cloudcost (internal-demo ops descriptors), and the
default-install referent `app/ai-app/deployment/bundles.yaml`. No bundle-secret
changes — the search key is a PLATFORM secret, present in all four env secret
stores.

Tests: bundle 170/170 (web tools shaping/pass-through/picker 8; budget
defaults/env/descriptor-overlay 4; per-invocation step signatures 2), SDK
frameworks 17/17. Repo commit: `a5ba15d09`.
