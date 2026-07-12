---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/multi-action/tool-execution-policy-README.md
title: "Tool Execution Policy"
summary: "Declarative tool traits for starting detached, neutral calls as soon as their streamed tool-call block is complete."
tags: ["sdk", "tools", "traits", "react", "streaming", "multi-action", "parallel"]
keywords: ["tool_traits", "execution", "tool_call_complete", "parallel_with_generation", "detached", "at_most_once_per_round", "early execution"]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/multi-action/tool-strategy-traits-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/online-strategic-governance-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/streaming/governed-streaming-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/work-with-subagents-README.md
---
# Tool Execution Policy

`tool_traits.execution` describes when and how a model-callable tool may run.
It is runtime policy, not a special case for one tool.

The first supported profile starts an independent call as soon as its complete
`tool_call` action has been parsed and validated, while the model continues
streaming later actions:

```yaml
tool_traits:
  strategy: [neutral]
  execution:
    trigger: tool_call_complete
    concurrency: parallel_with_generation
    result_dependency: detached
    replay: at_most_once_per_round
```

The policy is a mapping so later execution profiles can add fields without
changing the trait model. The current runtime activates early execution only
when all four fields match the supported profile and the strategy is exactly
`neutral`.

## Policy Fields

| Field | Current value | Contract |
| --- | --- | --- |
| `trigger` | `tool_call_complete` | Start only after one complete action block has yielded a parseable tool id and parameter object. |
| `concurrency` | `parallel_with_generation` | Run in a tracked task while the model may continue generating sibling actions. |
| `result_dependency` | `detached` | No action in the same round consumes this result. The result can still inform later rounds through normal timeline/tool-result state. |
| `replay` | `at_most_once_per_round` | Retries of the same turn/iteration/action slot reuse the first execution record instead of calling the tool again. |

`at_most_once_per_round` is deliberately precise. It protects model-provider
retries, compaction retries, and ReAct decision retries in the running turn. It
is not a replacement for provider-side idempotency across process failure.
Irreversible external APIs should also accept an idempotency key.

## Runtime Flow

```text
model stream
    |
    | complete <channel:action> block
    v
parse one tool call
    |
    +-- action overseer accepted this ordered action?
    +-- strategy is exactly neutral?
    +-- execution profile opts in?
    +-- protocol and tool signature valid?
    |
    v
deterministic round/action call id
    |
    +--> tracked tool task starts ----------------------+
    |                                                   |
    +--> model continues streaming sibling actions      |
                                                        |
generation finishes                                    |
    |                                                   |
    +--> wait for tracked calls to settle <-------------+
    |
    v
normal post-generation state machine
    |
    +-- counts the action and keeps its result
    +-- does not validate, call, or write it a second time
```

Live task objects are kept outside graph state. The graph state carries only a
serializable execution ledger: deterministic action key, call id, tool id,
round coordinates, semantic fingerprint, status, timing, and result/error.

The deterministic identity is based on `(turn_id, iteration, action_index)`.
Once an irreversible action starts, a retry cannot replace that slot with a
second side effect. A semantic fingerprint additionally recognizes the same
call if a provider retry moves it to another action index.

## Where The Trait Can Be Declared

A built-in tool can own the policy in its static tool specification:

```python
TOOL_SPEC = {
    "id": "example.notify",
    "tool_traits": {
        "strategy": ["neutral"],
        "execution": {
            "trigger": "tool_call_complete",
            "concurrency": "parallel_with_generation",
            "result_dependency": "detached",
            "replay": "at_most_once_per_round",
        },
    },
}
```

An application can apply the same policy to a configured Python, MCP, or
named-service tool connection:

```yaml
surfaces:
  as_consumer:
    agents:
      main:
        tools:
          - name: notifications
            kind: python
            module: example.notifications
            alias: notifications
            allowed: [start_background_notification]
            tool_traits:
              start_background_notification:
                strategy: [neutral]
                execution:
                  trigger: tool_call_complete
                  concurrency: parallel_with_generation
                  result_dependency: detached
                  replay: at_most_once_per_round
```

The configured callable name remains the key. There is no runtime list of
special tool ids.

## Safety Boundary

Opt in only when the tool satisfies all of these properties:

1. Its input is complete inside its own action block.
2. It does not consume a sibling action's output from the same round.
3. No sibling action in the same round consumes its result.
4. Starting it before the rest of the round is known is semantically valid.
5. Retrying the round must not repeat the side effect.

The runtime also requires `strategy: [neutral]`. A configured execution policy
on an exploration, exploitation, mixed, or unknown tool remains on the normal
post-generation path.

`react.delegate` is the first built-in user of this profile. Its tool call
schedules a child turn and returns a launch ticket; the parent can therefore
keep generating and later execute a sibling write while the child is already
working. The implementation still goes through the ordinary `ReactRound`
dispatcher and the existing delegate handler, so timeline blocks, accounting,
fork markers, queue admission, and error handling retain one authority.
