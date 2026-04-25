---
id: bundle_entrypoint
kind: concept
name: Bundle Entrypoint
aliases: [entrypoint, agentic_workflow class]
category: architectural
scope: framework
related: [bundle, react_loop, timeline]
realized_by:
  - kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint.BaseEntrypoint
  - kdcube_ai_app.apps.chat.sdk.examples.bundles.react.code@2026_03_29.entrypoint.ReactCodeWorkflow
  - kdcube_ai_app.apps.chat.sdk.solutions.chatbot.base_workflow.BaseWorkflow
pitfalls:
  - "The entrypoint's `__init__` is called once per process; per-turn state must live in the LangGraph state, not on `self`."
  - "`pre_run_hook` runs before every turn — putting expensive work there blocks the turn loop."
---

# Bundle Entrypoint

The **bundle entrypoint** is the class — decorated with `@agentic_workflow`
— that the platform instantiates to drive a bundle's turns. It wires the
bundle's tools, skills, and knowledge resources, builds a LangGraph
`StateGraph` whose nodes implement the bundle's logic, and exposes
`run(**params)` plus lifecycle hooks (`on_bundle_load`, `pre_run_hook`,
`post_run_hook`).

Entrypoints inherit from `BaseEntrypoint`, which standardises bundle
property loading, accounting, knowledge-space reconciliation, error
reporting, and turn metering. A bundle's distinct behaviour lives in its
graph nodes (typically a single `orchestrate` node delegating to a
`WithReact*Workflow` orchestrator), not in the entrypoint scaffolding.
