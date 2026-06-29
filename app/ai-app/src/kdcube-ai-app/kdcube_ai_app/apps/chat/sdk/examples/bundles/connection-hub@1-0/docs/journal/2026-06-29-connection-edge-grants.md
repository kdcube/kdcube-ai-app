---
date: 2026-06-29
title: "Connection Edge Grants"
status: implemented
---

# Connection Edge Grants

Telegram linking is now a real Connection Hub delegation edge, not a bare
identity link.

Before the browser claim writes the edge, the claim page shows an explicit
consent list. The backend computes that list from the signed-in KDCube platform
session and the platform role resolver. The selected grants are stored on the
edge.

Important grants:

- `identity:family` allows product reads, such as Memories, to aggregate across
  runtime user ids connected to the platform user.
- `economics:platform-user` allows economics to evaluate limits against the
  platform user while keeping Telegram as the actor identity.
- platform roles and permissions may be delegated only if the signed-in
  platform user currently has them and the user explicitly selects them.

An edge with no grants is still a proven connection, but it is intentionally
low-authority. It must not expand memory scope, derive platform roles, or use
platform economics.

The Mini App now warns when it sees an old or low-authority Telegram edge with
no delegated grants. The user can unlink and link again to choose capabilities.

