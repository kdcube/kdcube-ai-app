---
id: ks:docs/sdk/agents/claude/claude-code-README.md
title: "Claude Code Agent"
summary: "Native Python SDK runner for Claude Code with deterministic user and conversation binding, workspace-scoped execution, and communicator-backed streaming."
tags: ["sdk", "agents", "claude", "claude-code", "streaming", "communicator", "workspace"]
keywords: ["ClaudeCodeAgent", "run_followup", "run_steer", "allowedTools", "session-id", "stream-json", "ChatCommunicator"]
see_also:
  - ks:docs/sdk/bundle/bundle-runtime-README.md
  - ks:docs/sdk/streaming/channeled-streamer-README.md
  - ks:docs/sdk/tools/tool-subsystem-README.md
---
# Claude Code Agent

This page documents the native Python Claude Code runner added under:

- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/agent.py](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/agent.py)
- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/types.py](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/types.py)
- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/streaming.py](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/streaming.py)

Use this when a bundle or SDK component wants to run `claude` directly from Python without introducing a Node bridge or bundle-local subprocess glue.

## What it gives you

The SDK surface is:

- `ClaudeCodeAgent`
- `ClaudeCodeAgentConfig`
- `ClaudeCodeBinding`
- `ClaudeCodeRunResult`
- `ClaudeCodeTurnKind = "regular" | "followup" | "steer"`

Main features:

- native Python subprocess execution of `claude`
- deterministic Claude session binding from current KDCube user + conversation + agent name
- explicit caller-supplied workspace path
- explicit caller-supplied allowed tools
- incremental `chat.delta` emission through `ChatCommunicator`
- separate stderr step emission
- support for `regular`, `followup`, and `steer` turns

## Mental model

This runner is not a long-lived PTY session.

Each turn starts a fresh `claude -p` subprocess, but reuses a stable Claude `--session-id` so Claude Code can keep its own session continuity across turns.

That means:

- `run_turn(...)` starts a normal turn
- `run_followup(...)` continues the same Claude session
- `run_steer(...)` redirects the same Claude session

All three reuse the same workspace and deterministic Claude session id.

## Binding model

The runner binds itself from the current request context in:

- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/runtime/comm_ctx.py](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/runtime/comm_ctx.py)

It reads:

- `request_context.user.user_id`
- `request_context.user.fingerprint` as fallback
- `request_context.routing.conversation_id`
- `request_context.routing.session_id` as fallback

The deterministic Claude session id is derived as:

```python
uuid.uuid5(
    uuid.NAMESPACE_URL,
    f"kdcube/claude-code/{user_id}/{conversation_id}/{agent_name}",
)
```

So the effective session identity is:

- current user
- current conversation
- Claude agent name

This avoids cross-user session collisions while still allowing one user to run multiple Claude sessions by using different conversations or different agent names.

## Public API

Typical usage:

```python
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.solutions.claude_code import ClaudeCodeAgent

agent = ClaudeCodeAgent.from_current_context(
    agent_name="kb-writer",
    workspace_path=Path("/workspace/docs"),
    allowed_tools=["Read", "Grep", "Bash", "WebFetch", "WebSearch"],
)

result = await agent.run_turn(
    "Review the connected repos and propose the wiki structure."
)
```

Follow-up:

```python
followup = await agent.run_followup(
    "Continue, but focus only on installation and deployment sections."
)
```

Steer:

```python
steer = await agent.run_steer(
    "Change direction. Stop editing source repos and only prepare the output wiki repo."
)
```

## CLI invocation model

The runner executes Claude Code in print mode with stream-json:

```text
claude -p --verbose --output-format stream-json --include-partial-messages ...
```

Important current flags:

- `-p`
- `--verbose`
- `--output-format stream-json`
- `--include-partial-messages`
- `--allowedTools ...` when configured
- `--agent <agent_name>`
- `--session-id <stable-uuid>`

The CLI command is configurable through `ClaudeCodeAgentConfig.command`, but defaults to `claude`.

## Streaming behavior

Claude Code stream-json output is not token-by-token.

In practice the CLI often emits cumulative partial message snapshots. The SDK runner converts those snapshots into incremental suffix chunks before calling `self.comm.delta(...)`.

That logic lives in:

- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/streaming.py](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/streaming.py)

Communicator behavior:

- `chat.step` with `status="started"` when the turn begins
- `chat.delta` for each incremental Claude chunk
- `chat.step` on stderr lines when `emit_stderr_steps=True`
- `chat.step` with `status="completed"` or `status="error"` at the end

The runner does not call `chat.complete` itself. That remains the responsibility of the surrounding bundle or workflow turn handling.

## Result object

`ClaudeCodeRunResult` returns:

- `status`
- `session_id`
- `final_text`
- `delta_count`
- `exit_code`
- `stderr_lines`
- `raw_output_lines`
- `turn_kind`
- `agent_name`

This is meant for bundle logic and diagnostics, not only UI streaming.

## Workspace model

The caller must provide `workspace_path`.

The runner does not:

- clone repos
- create workspaces
- isolate concurrent worktrees
- publish or push changes

That is intentional. Workspace orchestration belongs to the caller or a higher-level SDK abstraction.

## Allowed tools

Allowed Claude Code tools are fully caller-controlled.

Example:

```python
agent = ClaudeCodeAgent.from_current_context(
    agent_name="repo-curator",
    workspace_path=workspace_path,
    allowed_tools=["Read", "Grep", "Bash", "WebFetch", "WebSearch"],
)
```

If `allowed_tools` is empty, the runner simply omits `--allowedTools`.

## Error behavior

Current behavior:

- invalid or missing workspace path raises before subprocess execution
- subprocess start failure emits an error step and re-raises
- non-zero Claude exit code returns `ClaudeCodeRunResult(status="failed", ...)`
- stderr lines are captured separately and also included in the final error step payload

The runner is designed so failures are visible both:

- in Python control flow
- in SSE / communicator diagnostics

## Current limitations

This first cut does not provide:

- PTY-backed interactive stdin sessions
- workspace isolation
- automatic secret injection policy
- automatic repo checkout lifecycle
- bundle UI integration

Those belong to higher-level integrations such as `kdcube.copilot`.

## Tests

Focused tests live in:

- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/tests/test_claude_code_agent.py](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/tests/test_claude_code_agent.py)

Covered cases:

- deterministic binding from current request context
- argument construction
- incremental snapshot-to-delta conversion
- stderr emission
- failure reporting
- session reuse across `followup` and `steer`

## Intended next use

The immediate consumer is the admin-only knowledge-base workflow planned for:

- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/kdcube.copilot@2026-04-03-19-05](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/kdcube.copilot@2026-04-03-19-05)

That bundle will use this SDK runner to:

- bind Claude Code execution to the current admin user
- keep conversation continuity across turns
- point Claude at caller-managed repo workspaces
- stream Claude output through the standard communicator path
