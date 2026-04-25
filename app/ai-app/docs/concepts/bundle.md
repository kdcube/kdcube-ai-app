---
id: bundle
kind: concept
name: Bundle
aliases: [plugin, agentic bundle]
category: architectural
scope: framework
related: [bundle_entrypoint, skill, knowledge_space, tool]
realized_by:
  - kdcube_ai_app.infra.plugin.bundle_registry.BundleSpec
  - kdcube_ai_app.apps.chat.sdk.examples.bundles.react.code@2026_03_29.entrypoint.ReactCodeWorkflow
pitfalls:
  - Bundle directories use `@<version>` suffixes; the loader treats them as a single logical id with versioned variants — do not collapse them.
  - A bundle's knowledge space is private to that bundle. Sharing a knowledge root across two bundles will cause index drift.
---

# Bundle

A **bundle** is the deployable unit in KDcube. It packages everything a chat
solution needs to run as a single, addressable artifact: an entrypoint
class, tool descriptors, skill descriptors, a knowledge space, and any
bundle-local agents or policies.

The platform discovers bundles by id (e.g. `react.code@2026-03-29`),
constructs their entrypoint, and routes turns through it. Bundles are
self-contained — two bundles in the same deployment are isolated from
each other in terms of knowledge, tools, and runtime state.

A bundle is *not* the same as the running workflow. The bundle is the
package on disk; the workflow (entrypoint instance + StateGraph + runtime
context) is what executes a turn.
