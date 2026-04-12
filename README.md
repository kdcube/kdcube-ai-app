# KDCube — Build and Ship End-to-End AI Apps Fast

KDCube is a self-hosted platform and SDK for building customer-facing AI apps as bundles.

A bundle is an application slice, not just a prompt or an agent wrapper. One bundle can combine:
- Python backend logic
- authenticated and public APIs
- widgets and a full custom UI
- React v2, Claude Code, and/or custom agents
- tools, skills, MCP, storage, props, and secrets
- scheduled jobs with `@cron(...)`
- dependency-isolated helpers with `@venv(...)`
- optional Node or TypeScript backend logic behind a Python bridge

KDCube gives you the runtime, streaming, isolation, memory, operations, and deployment model so you can ship real AI products, not just local agent demos.

![cubes.png](assets/cubes.png)

## Why Builders Use KDCube

- Build one bundle as a complete app slice: backend, APIs, streaming UX, widgets, and storage.
- Compose the right brains for each job: React v2, Claude Code, custom agents, tools, or isolated exec.
- Ship on a production runtime with multi-tenant isolation, backpressure, rate limits, economics, and observability.
- Keep provenance and recoverability: timelines, source pools, citations, artifacts, and rehydration.
- Prototype locally, then move to ECS and other hosted deployments without rewriting the app model.

## What You Build Here

The main unit in KDCube is a bundle.

A bundle can expose:
- chat behavior through `@on_message`
- authenticated APIs through `@api(route="operations")`
- anonymous or externally authenticated APIs through `@api(route="public")`
- widgets through `@ui_widget(...)`
- a full custom main UI through `@ui_main`
- scheduled logic through `@cron(...)`

Typical bundle structure:

```text
my.bundle@1-0/
  entrypoint.py
  orchestrator/
    workflow.py
  tools_descriptor.py
  skills_descriptor.py
  tools/
  skills/
  ui/
  ui-src/
  resources/
  tests/
  requirements.txt
  backend_bridge/
```

Python remains the KDCube-native shell. If you need selected backend logic in Node or TypeScript, keep the KDCube surface in Python and place the external backend behind a narrow bridge.

## Quickstart

Install the bootstrap CLI and launch the setup wizard:

```bash
pipx install kdcube-cli
kdcube
```

Alternative:

```bash
pip install kdcube-cli
kdcube
```

`kdcube-setup` remains available as a compatibility alias, but `kdcube` is the canonical command.

Prerequisites:
- Python 3.9+
- Git
- Docker

Start here:
- [CLI installer](app/ai-app/src/kdcube-ai-app/kdcube_cli/README.md)
- [CLI deployment docs](app/ai-app/docs/service/cicd/cli-README.md)
- [Docker Compose (all-in-one)](app/ai-app/deployment/docker/custom-ui-managed-infra/README.md)

## Start Here If You Want To Build Bundles

Read these in order:

1. [Bundle docs index](app/ai-app/docs/sdk/bundle/bundle-index-README.md)
2. [Bundle reference: `versatile`](app/ai-app/docs/sdk/bundle/bundle-reference-versatile-README.md)
3. [Bundle developer guide](app/ai-app/docs/sdk/bundle/bundle-dev-README.md)
4. [Bundle runtime](app/ai-app/docs/sdk/bundle/bundle-runtime-README.md)
5. [Bundle platform integration](app/ai-app/docs/sdk/bundle/bundle-platform-integration-README.md)
6. [Bundle props and secrets](app/ai-app/docs/sdk/bundle/bundle-props-secrets-README.md)

Primary reference bundle:
- [`versatile@2026-03-31-13-36`](app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/versatile@2026-03-31-13-36)

Specialized examples:
- [`kdcube.copilot@2026-04-03-19-05`](app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/kdcube.copilot@2026-04-03-19-05) for bundle-defined `ks:` knowledge space and builder copilot behavior
- [`with-isoruntime@2026-02-16-14-00`](app/ai-app/src/kdcube-ai-app/kdcube_ai_app/apps/chat/sdk/examples/bundles/with-isoruntime@2026-02-16-14-00) for direct isolated exec
- [Node/TS backend bridge reference](app/ai-app/docs/sdk/bundle/bundle-node-backend-bridge-README.md)

## Agent and Runtime Model

KDCube is not limited to one agent shape.

Inside one bundle you can use:
- React v2 for timeline-first orchestration, planning, ANNOUNCE, and tool-driven work
- Claude Code for workspace-scoped coding tasks with persistent session identity
- custom Python agents for domain-specific flows
- isolated exec for generated code and controlled execution
- `@venv(...)` for dependency-heavy Python leaf helpers

Important: React v2 is not based on provider-native tool-calling protocol. The loop is controlled by the platform runtime, not by a model-specific tool-call format. That lets you use non-tool-calling models as the reasoning brain when they can follow the ReAct contract.

Read more:
- [React docs](app/ai-app/docs/sdk/agents/react)
- [Claude Code integration](app/ai-app/docs/sdk/agents/claude/claude-code-README.md)
- [Bundle runtime](app/ai-app/docs/sdk/bundle/bundle-runtime-README.md)

## What the Platform Gives You

### Runtime and UX
- SSE / REST / Socket.IO chat transport
- channeled streaming and live widget updates
- bundle-owned widgets and full custom main-view UI
- session-aware relay and fan-out

### Execution and tools
- custom tools and MCP
- isolated Python execution
- optional Docker and Fargate execution paths
- bundle-scoped cached Python venvs for leaf work

### Memory, provenance, and artifacts
- timeline-first React runtime
- source pools and citations
- attachments and generated artifacts
- artifact rehydration and logical references

### Operations and safety
- multi-tenant / multi-project isolation
- gateway controls, rate limits, and backpressure
- budgets, economics, and accounting
- metrics and autoscaling support
- role-aware filtering and bundle UI authorization

## ReAct v2 in One Paragraph

KDCube’s React v2 agent is timeline-first. Tool calls, artifacts, plans, ANNOUNCE state, and turn history become structured runtime data rather than ephemeral model chatter. That gives the platform:
- stable memory and re-read paths
- cache-aware pruning and `react.hide`
- plan tracking with `react.plan`
- source-backed provenance
- collaboration through timeline and ANNOUNCE contributions

Deep dives:
- [React structure](app/ai-app/docs/sdk/agents/react/structure-README.md)
- [React plan](app/ai-app/docs/sdk/agents/react/plan-README.md)
- [React timeline](app/ai-app/docs/sdk/agents/react/timeline-README.md)

## Deployment Model

KDCube supports:
- local Docker Compose for development and small deployments
- EC2-style deployments
- ECS-based hosted deployments

The CLI supports:
- guided local setup
- descriptor-driven installs
- latest released builds
- upstream source builds
- local bundle prototyping and bundle reload flow

Read more:
- [CLI installer](app/ai-app/src/kdcube-ai-app/kdcube_cli/README.md)
- [Configuration docs](app/ai-app/docs/service/configuration)
- [Deployment docs](app/ai-app/docs/service/cicd)

## Documentation

Builder-oriented:
- [SDK bundle docs](app/ai-app/docs/sdk/bundle)
- [Bundle docs index](app/ai-app/docs/sdk/bundle/bundle-index-README.md)
- [Bundle reference bundle](app/ai-app/docs/sdk/bundle/bundle-reference-versatile-README.md)
- [Tools docs](app/ai-app/docs/sdk/tools)
- [Skills docs](app/ai-app/docs/sdk/skills)

Platform-oriented:
- [Architecture docs](app/ai-app/docs/arch)
- [Service docs](app/ai-app/docs/service)
- [Exec / isolation docs](app/ai-app/docs/exec)

## Community

If you want to build AI apps fast but still control runtime, tools, costs, deployment, and provenance, KDCube is aimed at that use case.

Project site:
- https://kdcube.tech/
