---
id: repo:kdcube-ai-app/app/ai-app/docs/service/synch-mechanisms/file-lock-README.md
title: "File Lock Compatibility Pointer"
summary: "Compatibility pointer for the old observed file lock page (formerly under service/fs/). The canonical service-level concurrency document is Synchronization Mechanisms, in this directory."
status: superseded
tags: ["service", "synch-mechanisms", "locks", "synchronization", "critical-section"]
keywords: ["file lock", "observed file lock", "synchronization mechanisms", "critical section"]
see_also:
  - repo:kdcube-ai-app/app/ai-app/docs/service/synch-mechanisms/critical-section-README.md
---
# File Lock Compatibility Pointer

This page moved.

The canonical document is now, in this same directory:

- [Synchronization Mechanisms](./critical-section-README.md)

Use that page for choosing between:

- Postgres advisory locks for database bootstrap and migrations;
- Redis locks for cluster-wide scheduled or runtime coordination;
- observed file locks for shared filesystem mutation.
