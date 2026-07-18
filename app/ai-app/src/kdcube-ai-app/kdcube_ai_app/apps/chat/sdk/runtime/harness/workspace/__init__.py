# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter
"""The agent-harness distributed turn workspace.

Every turn gets a per-turn workspace on the shared exec-workspace volume —
``work/`` + ``out/`` directories any worker can serve (turns hop machines;
nothing lives in process memory). Data is PULLED INTO it (user attachments,
files from earlier turns) and code execution PRODUCES new data out of it
(everything written under the artifact outdir is hosted back into the
conversation). The React agent and ported bundles stand on the SAME
workspace: same root (`get_exec_workspace_root`), same artifact layout, same
pull resolution.

Modules:
  * ``references`` — canonical ``conv:*`` owner refs and the mapping between
    durable ``conv:fi:`` identities and physical turn-workspace paths.
  * ``artifacts`` — framework-neutral produced/materialized workspace objects.
  * ``layout`` — the artifact directory contract (``artifact_outdir_for``),
    snapshots/diffs of produced files, and the item shapes hosting consumes.
  * ``pull``  — materialize conversation artifact refs (``conv:fi:``) as plain
    local files under a workspace directory (the framework-neutral core a
    pull tool wraps).
Import the scoped contract from its module, for example
``runtime.harness.workspace.references`` or
``runtime.harness.workspace.pull``. Layout symbols remain re-exported here
for the existing execution-runtime integration.
"""

from kdcube_ai_app.apps.chat.sdk.runtime.harness.workspace.layout import (
    ARTIFACT_OUTPUT_DIRNAME,
    ARTIFACT_OUTPUT_ENV,
    DEFAULT_IGNORE_NAMES,
    RUNTIME_OUTPUT_ENV,
    artifact_outdir_for,
    build_deleted_notices,
    build_items_from_diff,
    diff_snapshots,
    format_diff,
    resolve_artifact_path,
    runtime_outdir_for_artifact_outdir,
    should_skip_relpath,
    snapshot_outdir,
)
from kdcube_ai_app.apps.chat.sdk.runtime.harness.workspace.pull import (
    pull_refs_into_dir,
)
__all__ = [
    "ARTIFACT_OUTPUT_DIRNAME",
    "ARTIFACT_OUTPUT_ENV",
    "DEFAULT_IGNORE_NAMES",
    "RUNTIME_OUTPUT_ENV",
    "artifact_outdir_for",
    "build_deleted_notices",
    "build_items_from_diff",
    "diff_snapshots",
    "format_diff",
    "resolve_artifact_path",
    "runtime_outdir_for_artifact_outdir",
    "should_skip_relpath",
    "snapshot_outdir",
    "pull_refs_into_dir",
]
