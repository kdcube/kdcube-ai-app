---
id: skill
kind: concept
name: Skill
aliases: []
category: architectural
scope: framework
related: [bundle, tool]
realized_by:
  - kdcube_ai_app.apps.chat.sdk.skills.skills_registry.SkillSpec
pitfalls:
  - A skill is *not* a tool. Skills package related tools plus the prompt scaffolding that tells the agent how to use them.
  - Skill ids must be unique within a bundle; collisions silently overwrite the earlier registration.
---

# Skill

A **skill** is a reusable bundle of related tools plus the instructions that
explain when and how the agent should use them. Skills are declared in a
bundle's `skills_descriptor.py` via `SkillSpec` and registered with the
agent at bundle load.

A skill differs from a raw tool by carrying *intent*: the SkillSpec
includes a system prompt fragment that primes the agent to recognise the
tasks the skill is designed for, while the bundle of tools provides the
mechanical actions. The agent picks a skill, then the skill's tools, not
the other way around.
