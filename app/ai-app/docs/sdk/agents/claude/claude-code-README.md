---
id: ks:docs/sdk/agents/claude/claude-code-README.md
title: "Claude Code Agent"
summary: "Native Python SDK runner for Claude Code with deterministic user and conversation binding, workspace-scoped execution, communicator-backed streaming, framed structured-output parsing, timeout control, and correct session resume semantics."
tags: ["sdk", "agents", "claude", "claude-code", "streaming", "communicator", "workspace"]
keywords: ["ClaudeCodeAgent", "run_followup", "run_steer", "allowedTools", "session-id", "resume", "add-dir", "permission-mode", "stream-json", "ChatCommunicator", "timeout_seconds", "structured_output_prefixes"]
see_also:
  - ks:docs/sdk/bundle/bundle-runtime-README.md
  - ks:docs/sdk/streaming/channeled-streamer-README.md
  - ks:docs/sdk/tools/tool-subsystem-README.md
  - ks:docs/sdk/agents/claude/claude-code-accounting-README.md
  - ks:docs/sdk/agents/claude/claude-code-workspace-bootstrap-README.md
---
# Claude Code Agent

This page documents the native Python Claude Code runner added under:

- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/agent.py](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/agent.py)
- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/runtime.py](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/solutions/claude_code/runtime.py)
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
- `ClaudeCodeSessionStoreConfig`
- `run_claude_code_turn(...)`

Main features:

- native Python subprocess execution of `claude`
- deterministic Claude session binding from current KDCube user + conversation + agent name
- explicit caller-supplied workspace path
- explicit caller-supplied allowed tools
- explicit additional writable / accessible directories via `--add-dir`
- explicit Claude permission mode such as `acceptEdits`
- incremental `chat.delta` emission through `ChatCommunicator`
- optional framed structured-output extraction from streamed assistant text
- optional per-turn timeout
- separate stderr step emission
- support for `regular`, `followup`, and `steer` turns

## Mental model

This runner is not a long-lived PTY session.

Each turn starts a fresh `claude -p` subprocess, but reuses a stable Claude
session identity so Claude Code can keep its own continuity across turns.

That means:

- first turn uses `--session-id <stable-uuid>` to create the Claude session
- continued turns use `--resume <stable-uuid>` to continue that same session
- `run_followup(...)` and `run_steer(...)` always resume
- `run_turn(..., resume_existing=True)` is available when the caller wants a
  normal prompt shape but is continuing an already existing conversation

All of these reuse the same workspace and deterministic Claude session id.

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

Important distinction:

- `ClaudeCodeBinding.session_id` is the current KDCube request/session correlation id
- `ClaudeCodeBinding.claude_session_id` is the stable Claude resume identity

So browser session expiry or multi-device login changes do not break Claude Code session continuity. Continuity is anchored to `user_id + conversation_id + agent_name`, not to the transient KDCube session id.

## Public API

Typical usage:

```python
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.solutions.claude_code import ClaudeCodeAgent

agent = ClaudeCodeAgent.from_current_context(
    agent_name="kb-writer",
    workspace_path=Path("/workspace/docs"),
    model="claude-sonnet-4-6",
    allowed_tools=["Read", "Grep", "Bash", "WebFetch", "WebSearch"],
    additional_directories=[
        Path("/workspace/output-repo"),
        Path("/workspace/source-repo"),
    ],
    permission_mode="acceptEdits",
    timeout_seconds=900,
    structured_output_prefixes=("CLAUDE_EVENT",),
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

Continuing an existing conversation with a regular turn:

```python
result = await agent.run_turn(
    "Now push the prepared wiki branch.",
    resume_existing=True,
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
- `--model <alias|name>` when configured
- `--allowedTools ...` when configured
- `--permission-mode <mode>` when configured
- `--add-dir <path>` for each configured additional directory
- `--agent <agent_name>`
- `--session-id <stable-uuid>` for first turn
- `--resume <stable-uuid>` for continued turns

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

## Structured streamed output

Some callers need more than raw `final_text`. For that case the runner can parse
framed JSON records directly from streamed assistant text.

Configure:

- `ClaudeCodeAgentConfig.structured_output_prefixes`
- `ClaudeCodeAgentConfig.on_structured_output`
- `ClaudeCodeAgentConfig.on_text_chunk`

The intended contract is line-framed output, for example:

```text
CLAUDE_EVENT {"type":"phase","phase":"analysis","status":"started"}
CLAUDE_EVENT {"type":"warning","message":"fallback path activated"}
```

The prefix is caller-defined. The platform only enforces that parsing is
prefix-based; it does not reserve an application-specific event name.

The runner does not try to parse arbitrary JSON from normal prose. It only
parses lines beginning with one of the configured prefixes.

Parsed records are returned in `ClaudeCodeRunResult.structured_events` as:

```python
{
    "prefix": "CLAUDE_EVENT",
    "payload": {"type": "phase", "phase": "analysis", "status": "started"},
    "raw_line": 'CLAUDE_EVENT {"type":"phase","phase":"analysis","status":"started"}',
}
```

This is meant for workflows that need semantic progress while the turn is still
running, while still ending with one final result payload in `final_text`.

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
- `provider`
- `requested_model`
- `model`
- `usage`
- `cost_usd`
- `duration_ms`
- `api_duration_ms`
- `raw_result_event`
- `error_message`
- `timed_out`
- `timeout_seconds`
- `structured_events`

This is meant for bundle logic and diagnostics, not only UI streaming.

`requested_model` is what the caller asked Claude Code to use. `model` is what the CLI stream actually reported for the run. When aliases like `sonnet` or `opus` are used, this distinction is useful for observability and accounting.

## Model selection

`ClaudeCodeAgentConfig.model` is optional.

- if omitted or `"default"`, the runner starts Claude Code without `--model`
- if set, the runner forwards it via `claude --model <alias|name>`

This makes it possible for a bundle to persist a user-selected Claude model and reuse it across turns while still keeping the actual resolved model visible in the result object and accounting events.

## Accounting

Claude Code runs are accounted as normal `service_type=llm` usage events with:

- `provider="anthropic"`
- `metadata.runtime="claude_code"`
- resolved usage from the `stream-json` result stream

See [ks:docs/sdk/agents/claude/claude-code-accounting-README.md](ks:docs/sdk/agents/claude/claude-code-accounting-README.md).

## Workspace model

The caller must provide `workspace_path`.

The runner does not:

- clone repos
- create workspaces
- isolate concurrent worktrees
- publish or push changes

That is intentional. Workspace orchestration belongs to the caller or a higher-level SDK abstraction.

If the Claude run needs access outside the main workspace root, the caller
should pass `additional_directories`. These are forwarded to Claude Code as
`--add-dir` entries.

## Session-store bootstrap

Claude workspace/session continuity is now handled by a separate runtime layer,
not by the low-level runner itself.

Use:

- `run_claude_code_turn(...)`
- `ClaudeCodeSessionStoreConfig`

when the caller wants:

- a bundle-controlled local Claude root
- optional git bootstrap before a regular turn
- optional publish after the turn

That layer supports:

- `CLAUDE_CODE_SESSION_STORE_IMPLEMENTATION=local|git`
- `CLAUDE_CODE_SESSION_GIT_REPO=<repo>`

See [ks:docs/sdk/agents/claude/claude-code-workspace-bootstrap-README.md](ks:docs/sdk/agents/claude/claude-code-workspace-bootstrap-README.md).

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

## Permission mode

The runner exposes Claude Code permission mode through
`ClaudeCodeAgentConfig.permission_mode` and
`ClaudeCodeAgent.from_current_context(..., permission_mode=...)`.

Current default:

- `acceptEdits`

This is useful for managed workspaces where the caller wants Claude to edit
within the allowed workspace / `--add-dir` scope without stopping on each file
write.

## Error behavior

Current behavior:

- invalid or missing workspace path raises before subprocess execution
- subprocess start failure emits an error step and re-raises
- non-zero Claude exit code returns `ClaudeCodeRunResult(status="failed", ...)`
- per-turn timeout marks the run as failed and terminates the Claude subprocess
- stderr lines are captured separately and also included in the final error step payload
- final error step payload includes:
  - `last_stderr_line`
  - `raw_result_event`
  - `timed_out`
  - `timeout_seconds`

The runner is designed so failures are visible both:

- in Python control flow
- in SSE / communicator diagnostics

## Current limitations

This first cut does not provide:

- PTY-backed interactive stdin sessions
- workspace isolation
- automatic secret injection policy
- bundle UI integration

The generic runner still does not itself own repo bootstrap/publish policy. That
is handled by the higher-level Claude workspace/session-store runtime layer.

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
- first-turn `--session-id` vs resumed-turn `--resume`
- session reuse across `followup` and `steer`
- git-backed session bootstrap/publish through `run_claude_code_turn(...)`

## Intended next use

The immediate consumer is the admin-only knowledge-base workflow planned for:

- [src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/kdcube.copilot@2026-04-03-19-05](../../../../src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/kdcube.copilot@2026-04-03-19-05)

That bundle will use this SDK runner to:

- bind Claude Code execution to the current admin user
- keep conversation continuity across turns
- point Claude at caller-managed repo workspaces
- stream Claude output through the standard communicator path
- optionally persist Claude's own session substrate through the git-backed session store
