---
id: repo:kdcube-ai-app/app/ai-app/docs/sdk/agents/react/online-strategic-governance-README.md
title: "ReAct Online Strategic Governance"
summary: "How ReAct uses governed streaming, tool strategy traits, and ordered action policy to stop invalid moves while generation is still streaming."
tags: ["sdk", "agents", "react", "streaming", "multi-action", "tool-traits", "governance"]
keywords:
  - "online strategic governance"
  - "RoundActionOverseer"
  - "tool strategy traits"
  - "exploration"
  - "exploitation"
  - "neutral"
  - "unknown"
  - "multi-action harness"
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/streaming/governed-streaming-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/multi-action/README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/solutions/multi-action/tool-strategy-traits-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/sdk/tools/tool-subsystem-README.md
  - repo:kdcube-ai-app/app/ai-app/docs/configuration/bundle-runtime-configuration-and-secrets-README.md
---
# ReAct Online Strategic Governance

ReAct online strategic governance is the ReAct-specific use of governed
streaming. It watches streamed action decisions while the model is still
generating, classifies the move, and stops incompatible same-round action
sequences before the user waits for invalid output.

The generic mechanism is described in
[Governed Streaming](../../streaming/governed-streaming-README.md). This
document explains the ReAct policy that runs on top of it.

## Why ReAct Needs Online Governance

ReAct tool results are only known after the current action round completes. If
the model emits:

```text
web_search -> react.write
```

in one round, the write cannot truthfully use the search result. The result has
not run yet. Waiting for a large `react.write` payload would waste tokens and
make the user wait for a move the harness already knows must be rejected.

So ReAct governs the stream online:

```text
detect move identity early
  -> judge against accepted moves
  -> open or deny stream gate
  -> interrupt immediately on denied move
```

## Runtime Actors

```text
React decision model
  owns: streamed channel text
  emits: <channel:action> JSON, <channel:code>, thinking, summary

versatile_streamer_v3.stream_with_channels
  owns: channel parsing and subscriber dispatch

TimelineStreamer
  owns: incremental JSON path sniffing for action channel
  detects: action, tool_call.tool_id, final-answer lane

RoundActionOverseer
  owns: accepted action list for this round
  receives: detected action identity
  applies: ordered strategy/final-answer policy

ActionStreamGate
  owns: pending visible deltas for one action lane

React runtime
  owns: protocol violation recording, retry state, tool execution
```

Data flow:

```text
Model.delta
  -> stream_with_channels.channel(action, instance=i)
  -> TimelineStreamer.path_sniffer
  -> detected_move(i, action, tool_id)
  -> RoundActionOverseer.policy
  -> gate allow/deny
  -> visible timeline/canvas stream OR StreamPolicyViolation
```

## Move Identity

The ReAct action channel is JSON. The sniffer does not need a full parsed JSON
object before it can identify the move.

For tool calls:

```text
root.action = "call_tool"
root.tool_call.tool_id = "<tool id>"
```

For final close:

```text
root.action = "complete" | "exit"
```

The important design point is that identity should appear before large payloads.
Normal tool-call JSON does this:

```json
{
  "action": "call_tool",
  "tool_call": {
    "tool_id": "react.write",
    "params": {
      "path": "files/report.md",
      "content": "..."
    }
  }
}
```

Once `react.write` is identified, the policy can reject or allow without
waiting for `params.content`.

## Strategy Traits

The strategy trait is attached to concrete model-callable tools.

```text
exploration   obtains information
exploitation  writes, mutates, produces durable output, or commits a result
neutral       bookkeeping or side information
unknown       no strategy trait reached the runtime
```

Tool traits come from:

```text
tool code decorator
  @tool_trait(strategy=["exploration"])

consumer config
  surfaces.as_consumer.agents.<agent>.tools[].tool_traits
```

Consumer config is the deployment policy and can override decorator-provided
traits for that agent.

Example:

```yaml
surfaces:
  as_consumer:
    agents:
      main:
        tools:
          - id: web
            kind: python
            module: kdcube_ai_app.apps.chat.sdk.tools.web_tools
            alias: web_tools
            allowed: [web_search, web_fetch]
            tool_traits:
              web_search:
                strategy: [exploration]
              web_fetch:
                strategy: [exploration]

          - id: rendering
            kind: python
            module: kdcube_ai_app.apps.chat.sdk.tools.rendering_tools
            alias: rendering_tools
            allowed: [write_pdf]
            tool_traits:
              write_pdf:
                strategy: [exploitation]
```

The ReAct catalog renders traits in the tool scope:

```text
Scope:
    - strategy: exploration
```

## Ordered Matrix

Policy is ordered:

```text
first valid action:
  admitted

candidate action n:
  checked against every previously accepted action 0..n-1
```

The current runtime cap is two actions per round. The algorithm is intentionally
general so a future cap can be raised without changing the core judgment rule.

```text
                    following candidate action
accepted earlier    exploration  exploitation  neutral  unknown
exploration         ok           no            ok       no
exploitation        ok           ok            ok       no
neutral             ok           ok            ok       no
unknown             no           no            no       no
```

Unknown tools run alone. If the runtime cannot see a strategy, it cannot prove
same-round compatibility.

The matrix is ordered. `exploration -> exploitation` is denied because the later
exploitation would consume evidence that will not be visible until the next
round. `exploitation -> exploration` is allowed for staged work: the model can
finish an already-supported write/render/patch and then start additional or
next-step research whose result will be inspected later.

## Final Close Policy

`complete` and `exit` are not normal tools. They close the turn.

Rules:

```text
call_tool with embedded final_answer:
  keep the tool
  suppress final_answer
  record protocol_violation.final_answer_with_tool_call

non-neutral tool -> complete/exit:
  keep the tool
  reject the final close
  final answer is not shown

complete/exit -> non-neutral tool:
  keep the final close
  reject the later tool

neutral tool <-> complete/exit:
  allowed
```

This keeps the same ordered judgment principle: earlier accepted work survives;
the incompatible later move is dropped.

## Example 1: Search Then Write

Input stream:

```text
<channel:action>
{"action":"call_tool","tool_call":{"tool_id":"web_tools.web_search", ...}}
</channel:action>

<channel:action>
{"action":"call_tool","tool_call":{"tool_id":"react.write", ...large content...}}
</channel:action>
```

Runtime:

```text
web_tools.web_search
  strategy = exploration
  first action = accepted
  gate opens

react.write
  strategy = exploitation
  candidate after exploration = rejected
  gate denied
  StreamPolicyViolation raised
```

User sees:

```text
web_search action/trace
web_search result after tool execution
protocol violation: react.write was incompatible and was not shown or run
```

User does not see:

```text
partial react.write JSON
partial react.write content
final answer that pretends to use the search result
```

The model stream is interrupted as soon as `react.write` is identified. The
runtime does not wait for the large write payload to finish.

## Example 2: Write With Embedded Final Answer

Input:

```json
{
  "action": "call_tool",
  "tool_call": {
    "tool_id": "react.write",
    "params": {
      "path": "files/report.md",
      "content": "..."
    }
  },
  "final_answer": "Done."
}
```

Runtime:

```text
react.write action = accepted
embedded final_answer = suppressed
tool executes
protocol notice is recorded
```

The user sees the write action and its result. The user does not see `Done.`
as a final answer in that round.

## Example 3: Neutral Then Final

Input:

```text
memory.record_memory -> complete
```

If `memory.record_memory` is configured as `strategy: [neutral]`, this pair is
allowed:

```text
neutral -> final close = allowed
```

The neutral action can run and the final answer can close the turn.

## Interrupt Path

ReAct online governance uses the stream-policy interruption path from governed
streaming:

```text
TimelineStreamer detects move
  -> RoundActionOverseer rejects
  -> gate.deny()
  -> raise StreamPolicyViolation
  -> stream_with_channels re-raises
  -> React runtime catches
  -> interrupted generation snapshot is stashed
  -> protocol violation is recorded
  -> retry state is returned
```

This is not steer cancellation. Steer cancels an active async task from an
external event. Strategic governance aborts from inside the model stream
callback when the stream itself reveals a forbidden move.

## Implementation Anchors

- `runtime/tool_traits.py`
- `runtime/tool_config.py`
- `runtime/tool_subsystem.py`
- `solutions/react/call.py`
- `solutions/react/layout.py`
- `solutions/react/v3/action_overseer.py`
- `solutions/react/v3/runtime.py`
- `solutions/widgets/canvas.py::TimelineStreamer`
- `streaming/stream_policy.py`
- `streaming/versatile_streamer_v3.py`
