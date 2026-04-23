---
id: ks:docs/sdk/bundle/build/sync-tier1-bundle-docs-to-build-with-kdcube-plugins-README.md
title: "Tier 1 Bundle Agent Contract For Build-With-KDCube Plugins"
summary: "Implementation-agnostic handoff for the Claude Code and Codex plugin engineers describing the agent roles we expect, the Tier 1 bundle-doc resources we provide, and the routing behavior the plugin must expose."
tags: ["sdk", "bundle", "plugins", "claude-code", "codex", "handoff", "tier-1"]
keywords: ["plugin docs sync", "bundle agent contract", "claude code plugin", "codex plugin", "build with kdcube", "tier 1 bundle docs", "bundle authoring reading order", "bundle configurator docs", "bundle deployer docs", "bundle qa docs", "agent roles and resources", "obsolete doc names"]
see_also:
  - ks:docs/sdk/bundle/build/how-to-navigate-kdcube-docs-README.md
  - ks:docs/sdk/bundle/build/how-to-write-bundle-README.md
  - ks:docs/configuration/bundle-runtime-configuration-and-secrets-README.md
  - ks:docs/sdk/bundle/build/how-to-configure-and-run-bundle-README.md
  - ks:docs/sdk/bundle/build/how-to-test-bundle-README.md
  - ks:docs/sdk/bundle/bundle-index-README.md
---
# Tier 1 Bundle Agent Contract For Build-With-KDCube Plugins

This note is for the developers maintaining the Claude Code plugin and the
Codex plugin for "build with KDCube".

The current plugin tree in source control may be outdated and is not the point
of this document.

The implementation may change.
The agent contract below should not.

## Goal

Both plugins must route users through the same Tier 1 bundle-doc path and must
expose the same role model.

This note is not mainly about file synchronization.

It is about two things:

1. which jobs we expect the agent to perform
2. which Tier 1 resources we give the agent for those jobs

## Agent Roles The Plugin Must Support

The agent should be able to operate in all of these roles:

- creator:
  builds a bundle from scratch
- integrator:
  wraps an existing backend, frontend, webhook, cron job, or tool into a
  KDCube bundle
- configurator:
  maps existing application settings into platform settings, bundle props,
  bundle secrets, and user-scoped state
- deployer:
  wires a bundle into one KDCube environment, operates descriptors, starts or
  stops the local runtime, and reloads bundles
- local QA:
  runs syntax checks, shared suite checks, and bundle-local tests
- integration QA:
  validates widget, API, MCP, reload, and cron/runtime behavior inside a real
  KDCube environment
- document reader:
  navigates the docs efficiently and chooses the next document intentionally

## Tier 1 Resources The Plugin Must Give The Agent

These five docs are now the primary Tier 1 path:

1. [how-to-navigate-kdcube-docs-README.md](how-to-navigate-kdcube-docs-README.md)
2. [how-to-write-bundle-README.md](how-to-write-bundle-README.md)
3. [../../../configuration/bundle-runtime-configuration-and-secrets-README.md](../../../configuration/bundle-runtime-configuration-and-secrets-README.md)
4. [how-to-configure-and-run-bundle-README.md](how-to-configure-and-run-bundle-README.md)
5. [how-to-test-bundle-README.md](how-to-test-bundle-README.md)

Interpretation:

- `how-to-navigate-kdcube-docs`:
  first router for all roles
- `how-to-write-bundle`:
  creator/integrator guide
- `bundle-runtime-configuration-and-secrets`:
  configurator guide
- `how-to-configure-and-run-bundle`:
  deployer/integrator runtime guide
- `how-to-test-bundle`:
  local QA and integration QA guide

## Required Plugin Behavior

The plugins should no longer treat the old scattered doc set as the primary
bundle-authoring path.

Instead:

- start with the 5 Tier 1 docs above
- use the navigation doc as the first router when the user has not yet said
  whether they are:
  - creating a new bundle
  - wrapping existing code into a bundle
  - configuring bundle settings and secrets
  - integrating or deploying a bundle into a KDCube environment
  - doing local QA or integration QA
  - browsing docs to determine the next read
- branch into deeper docs only when the question becomes specific

The plugin should not force the agent to read a large random doc set up front.

The plugin should first identify the role, then route to the right Tier 1 page,
then branch deeper only if needed.

## Minimum Reading Order The Plugins Must Expose

1. `how-to-navigate-kdcube-docs-README.md`
2. `how-to-write-bundle-README.md`
3. `docs/configuration/bundle-runtime-configuration-and-secrets-README.md`
4. `how-to-configure-and-run-bundle-README.md`
5. `how-to-test-bundle-README.md`

Then only if needed:

- `docs/sdk/bundle/bundle-platform-integration-README.md`
- `docs/sdk/bundle/bundle-runtime-README.md`
- `docs/sdk/bundle/versatile-reference-bundle-README.md`
- `docs/sdk/bundle/bundle-delivery-and-update-README.md`

## Role-To-Resource Mapping

| Agent role | First Tier 1 doc | Why |
| --- | --- | --- |
| creator | `how-to-write-bundle-README.md` | bundle shape, lifecycle, surfaces, wrapper strategy |
| integrator | `how-to-write-bundle-README.md` | integration boundary and wrapper design |
| configurator | `docs/configuration/bundle-runtime-configuration-and-secrets-README.md` | scope, ownership, and helper selection |
| deployer | `how-to-configure-and-run-bundle-README.md` | descriptors, workdir, local runtime, reload/start/stop |
| local QA | `how-to-test-bundle-README.md` | syntax, shared suite, bundle-local tests |
| integration QA | `how-to-test-bundle-README.md` | browser/API/MCP/reload/cron validation |
| document reader | `how-to-navigate-kdcube-docs-README.md` | explicit routing instead of random reading |

## Role-Based Routing

### If the user wants to create a new bundle

Start with:

1. `how-to-navigate-kdcube-docs-README.md`
2. `how-to-write-bundle-README.md`
3. `docs/configuration/bundle-runtime-configuration-and-secrets-README.md`

### If the user wants to wrap existing backend, UI, webhook, or cron code

Start with:

1. `how-to-navigate-kdcube-docs-README.md`
2. `how-to-write-bundle-README.md`
3. `docs/configuration/bundle-runtime-configuration-and-secrets-README.md`

Then branch to:

- `bundle-platform-integration-README.md`
- `versatile-reference-bundle-README.md`

### If the user wants to model app settings, bundle props, secrets, or user state

Start with:

1. `how-to-navigate-kdcube-docs-README.md`
2. `docs/configuration/bundle-runtime-configuration-and-secrets-README.md`
3. `how-to-configure-and-run-bundle-README.md`

### If the user wants to run or integrate a bundle locally

Start with:

1. `how-to-navigate-kdcube-docs-README.md`
2. `docs/configuration/bundle-runtime-configuration-and-secrets-README.md`
3. `how-to-configure-and-run-bundle-README.md`

Then branch to:

- `bundles-descriptor-README.md`
- `bundles-secrets-descriptor-README.md`
- `bundle-delivery-and-update-README.md`

### If the user wants local QA or integration QA

Start with:

1. `how-to-navigate-kdcube-docs-README.md`
2. `how-to-test-bundle-README.md`

### If the user is mainly trying to understand where to read next

Start with:

1. `how-to-navigate-kdcube-docs-README.md`

## Old References That Must Be Removed Or Replaced

If the plugin prompts, skills, or READMEs still reference these old docs, they
must be updated:

- `docs/sdk/bundle/bundle-dev-README.md`
  -> `docs/sdk/bundle/bundle-developer-guide-README.md`
- `docs/sdk/bundle/bundle-reference-versatile-README.md`
  -> `docs/sdk/bundle/versatile-reference-bundle-README.md`
- `docs/sdk/bundle/bundle-props-secrets-README.md`
  -> `docs/configuration/bundle-runtime-configuration-and-secrets-README.md`
- `docs/sdk/bundle/bundle-ops-README.md`
  -> `docs/sdk/bundle/bundle-delivery-and-update-README.md`
- `docs/service/configuration/runtime-read-write-contract-README.md`
  -> `docs/configuration/runtime-read-write-contract-README.md`

More important than the filename changes:

- those old docs should no longer define the primary reading path
- the 5 Tier 1 docs above now define the entry contract

## Where To Apply The Sync

Apply this sync to whatever the plugin currently uses, for example:

- system prompt or plugin prompt
- bundle-builder skill
- onboarding README
- docs links embedded in the plugin
- Codex plugin instructions or equivalent skill files

The current plugin tree is not assumed to be stable, so this note does not rely
on one specific implementation layout.

## What Success Looks Like

The engineer implementing the plugin should be able to answer all of these from
this note alone:

- which agent roles must the plugin support
- which Tier 1 docs are the mandatory starting resources
- which doc is first for each role
- which older references must be removed
- which deeper docs are only second-level resources

## Acceptance Criteria

The plugin sync is done when all of this is true:

- the plugin no longer points to removed bundle doc filenames
- the plugin starts bundle-authoring users with the 5 Tier 1 docs
- the plugin uses the navigation doc as the first router when task type is
  still ambiguous
- the plugin still links deeper docs only as second-level references
- Claude and Codex plugin variants expose the same Tier 1 reading order
