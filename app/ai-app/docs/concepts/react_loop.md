---
id: react_loop
kind: concept
name: ReAct Loop
aliases: [react agent, react v2, ReAct decision loop]
category: runtime
scope: framework
related: [bundle_entrypoint, timeline, channeled_streamer]
realized_by:
  - kdcube_ai_app.apps.chat.sdk.solutions.react.v2.runtime.ReactSolverV2
pitfalls:
  - Per-turn state belongs in the timeline, not on the agent class. State stored on the agent leaks across turns.
  - The decision agent must emit a structured-decision channel; missing channels stall the loop without a tool call to commit.
---

# ReAct Loop

The **ReAct loop** is KDcube's single-agent reasoning + acting loop. Each
round of the loop renders the conversation timeline, asks the LLM for the
next action via a structured-decision channel, executes the chosen tool
(or finalises the answer), contributes the result back into the timeline,
and iterates until the agent produces a final answer or budgets are
exhausted.

The loop is implemented by `ReactSolverV2`. Unlike multi-agent pipelines,
one agent drives the entire turn: there is no separate planner,
coordinator, or final-answer generator. An optional lightweight gate
agent runs only for new conversations to extract a title.

Every reason / act / observe step is a discrete, inspectable block in the
timeline. This is where governance attaches — budget caps, tenant
boundaries, policy gates, and approval checkpoints live at step
boundaries, not inside opaque prompt internals.
