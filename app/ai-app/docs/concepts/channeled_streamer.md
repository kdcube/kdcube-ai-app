---
id: channeled_streamer
kind: concept
name: Channeled Streamer
aliases: [multi-channel streaming, channel router]
category: streaming
scope: framework
related: [react_loop, timeline]
realized_by:
  - kdcube_ai_app.apps.chat.sdk.streaming.versatile_streamer.ChannelSpec
  - kdcube_ai_app.apps.chat.sdk.streaming.versatile_streamer.ChannelResult
  - kdcube_ai_app.apps.chat.sdk.streaming.versatile_streamer.ChannelSubscribers
  - kdcube_ai_app.apps.chat.sdk.streaming.artifacts_channeled_streaming.CompositeJsonArtifactStreamer
pitfalls:
  - Citation tokens are replaced *per channel* at stream time. Stored raw output is never rewritten — debugging tools that read the persisted stream see the original `[[S:n]]` tokens.
  - Channel subscribers run concurrently with the primary emit; long-running subscriber work blocks neither the stream nor the agent, but exceptions are swallowed unless explicitly surfaced.
---

# Channeled Streamer

The **channeled streamer** is a tag-based protocol that routes a single
LLM stream into multiple named logical channels — each with its own
format, citation-replacement policy, and subscriber fanout. It lets a
single completion deliver, in parallel, a thinking trace, a user-facing
markdown answer, a JSON follow-up list, a structured canvas artifact, a
usage sidecar, and an internal structured-decision payload.

Channels are declared as XML-like tags inside the LLM output:

```
<channel:thinking>...</channel:thinking>
<channel:answer>...</channel:answer>
<channel:followups>[...]</channel:followups>
<channel:canvas>{...}</channel:canvas>
```

The streamer parses incrementally and emits per-channel deltas; markdown
and text channels get live citation token replacement, while JSON
channels are accumulated and validated against Pydantic models.

`ChannelSubscribers` is the factory for side-effect handlers attached
to a specific channel — typical use cases include writing usage rows to
the timeline, mirroring the answer to the chat host, or persisting a
canvas artifact.
