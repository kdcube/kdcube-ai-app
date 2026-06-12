---
name: preferences
id: preferences
description: |
  Use stored per-user preferences, choices, interests, and profile facts before
  personalizing the answer. The reference bundle uses the SDK durable-memory
  tool surface for model-visible reads and writes. Treat this as a real memory
  workflow, not as optional flavor.
version: 1.0.0
category: product-knowledge
tags:
  - preferences
  - personalization
  - bundle-local
when_to_use:
  - The user asks for a personalized recommendation or answer
  - The user refers to prior likes, dislikes, or formatting preferences
  - The user continues a recurring task where remembered choices should apply
  - The user reveals a durable preference, fact, constraint, or correction
  - The agent wants to keep responses consistent with stored user preferences
  - The user asks what the bundle knows or remembers about them
  - The user asks about remembered city, location, timezone, preferred name, answer style, diet, or interests
  - The user asks to verify, update, or correct previously stored profile facts
author: kdcube
created: 2026-03-31
namespace: product
---

# Preference Skill

Treat the SDK memory tools as the user's evolving notes:
- preferences
- stable choices
- recurring formatting/style requests
- interests and dislikes
- durable profile facts or constraints that should matter in future turns

Before giving a personalized or user-specific answer, check whether the bundle already knows something relevant.

Important default:
- If the user asks a question that is naturally about stored long-term user memory, start with `memory.search_memory(...)` or `memory.recent_memories(...)` before answering.
- Do not rely only on short chat context for questions like:
  - "what do you know about me?"
  - "what city do you have for me?"
  - "what name should you call me?"
  - "what preferences did you save?"
  - "what food / style / timezone / location do you remember?"

Use:
- `memory.search_memory(...)` to inspect stored durable user memory with relevant keywords or labels
- `memory.recent_memories(...)` when the user asks broadly what is remembered
- `memory.record_memory(...)` when the user reveals or corrects a durable preference/fact
- `memory.confirm_memory(...)` when a new statement reinforces an existing memory
- `memory.retire_memory(...)` when the user asks to forget or invalidate an existing memory

Rules:
- Do not claim a preference exists unless the tool returned it.
- On preference-sensitive turns, prefer a small keyword-filtered lookup before broad personalization.
- On memory-check turns, do the lookup first and answer from the lookup result.
- If the user asks what is stored or remembered, do not answer from inference or from the current chat window alone.
- For common profile dimensions such as city, location, timezone, preferred name, answer style, diet, dislikes, and interests, treat the lookup as the normal first action.
- When the user explicitly reveals a durable preference, choice, constraint, interest, dislike, or profile fact, store it in the same turn instead of relying only on automatic capture.
- Prefer `memory.record_memory(...)` for new durable observations and corrections.
- Do not save transient one-off requests that are only relevant to the current reply.
- If no preference is stored, continue normally instead of fabricating one.
- If the tool returns no stored value for a memory-check question, say so plainly and optionally offer to save it now.

Examples:
- If the user asks for recommendations, first look up relevant stored preferences.
- If the user asks "what city do you have for me?" call `memory.search_memory(...)` with city/location/timezone terms before answering.
- If the user asks "what do you remember about me?" call `memory.recent_memories(...)` before summarizing.
- If the user says "I prefer concise bullet answers" or "my timezone is Europe/Berlin", capture that.
- If the user says "I live in Wuppertal now" or "please call me Elena", save that in the same turn.
- If the user corrects a remembered value, update it explicitly with `memory.record_memory(...)`.
