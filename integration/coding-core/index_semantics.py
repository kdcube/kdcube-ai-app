#!/usr/bin/env python
"""
Semantic-layer indexer.

Reads concept/policy markdown from configured roots and writes :Semantic
nodes (+ EMBODIES / EMBODIED_BY / GOVERNED_BY / RELATED_TO edges) to Neo4j.

Run from the repo containing `coding-core/`:

    python coding-core/index_semantics.py
    python coding-core/index_semantics.py --clear-first
    python coding-core/index_semantics.py --root path/to/extra/concepts

Reads:
  - coding-core/config.json   for DB creds + semantic.concept_roots etc.
  - configured roots          for the actual *.md files to ingest
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Make `extraction.*` and `graph.*` importable when run as a script.
sys.path.insert(0, str(Path(__file__).parent.resolve()))

from neo4j import GraphDatabase

from extraction.semantic_extractor import (  # noqa: E402
    DEFAULT_SCOPE,
    load_semantic_records,
)
from graph.schema import CONSTRAINTS, INDEXES, FULLTEXT_INDEXES, VECTOR_INDEXES  # noqa: E402
from graph.writers import (  # noqa: E402
    clear_semantic_layer,
    write_semantic_governs,
    write_semantic_nodes,
    write_semantic_realized_by,
    write_semantic_related,
)


log = logging.getLogger("coding-core-semantics")


def _load_config(coding_core_dir: Path) -> dict:
    cfg_path = coding_core_dir / "config.json"
    with open(cfg_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_roots(project_root: Path, raw_roots: list[str]) -> list[Path]:
    out = []
    for raw in raw_roots:
        p = Path(raw)
        if not p.is_absolute():
            p = project_root / raw
        out.append(p.resolve())
    return out


def _resolve_bundle_glob(project_root: Path, glob_pattern: str | None) -> list[Path]:
    if not glob_pattern:
        return []
    base = project_root
    parts = Path(glob_pattern).parts
    # Walk up to the first non-glob segment as the search root.
    fixed = []
    glob_tail: list[str] = []
    for i, part in enumerate(parts):
        if any(ch in part for ch in "*?["):
            glob_tail = list(parts[i:])
            break
        fixed.append(part)
    fixed_root = base.joinpath(*fixed) if fixed else base
    if not fixed_root.exists():
        return []
    if not glob_tail:
        return [fixed_root.resolve()] if fixed_root.is_dir() else []
    pattern = "/".join(glob_tail)
    return sorted({p.resolve() for p in fixed_root.glob(pattern) if p.is_dir()})


def _ensure_schema(session, dims: int) -> None:
    for stmt in CONSTRAINTS:
        if "Semantic" in stmt:
            session.run(stmt)
    for stmt in INDEXES:
        if "Semantic" in stmt or "semantic_" in stmt:
            session.run(stmt)
    for stmt in FULLTEXT_INDEXES:
        if "Semantic" in stmt or "semantic_" in stmt:
            session.run(stmt)
    for stmt in VECTOR_INDEXES:
        if "Semantic" in stmt or "semantic_" in stmt:
            session.run(stmt, dims=dims)


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest semantic-layer markdown into Neo4j")
    parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Extra root directory to scan (in addition to config.semantic.concept_roots)."
             " May be repeated.",
    )
    parser.add_argument(
        "--scope",
        default=DEFAULT_SCOPE,
        help="Default scope for files lacking an explicit `scope` frontmatter field.",
    )
    parser.add_argument(
        "--clear-first",
        action="store_true",
        help="Delete existing :Semantic nodes before ingesting.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse files and print summary; do not write to Neo4j.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on the first malformed file instead of skipping with a warning.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    coding_core_dir = Path(__file__).parent.resolve()
    cfg = _load_config(coding_core_dir)

    db_cfg = cfg.get("database") or {}
    target_cfg = cfg.get("target") or {}
    sem_cfg = cfg.get("semantic") or {}
    emb_cfg = cfg.get("embedding") or {}

    project_root = Path(target_cfg.get("project_root") or coding_core_dir.parent).resolve()

    declared_roots: list[str] = list(sem_cfg.get("concept_roots") or [])
    bundle_glob = sem_cfg.get("bundle_concept_glob")
    cli_roots = list(args.root)

    roots: list[Path] = []
    roots += _resolve_roots(project_root, declared_roots)
    roots += _resolve_bundle_glob(project_root, bundle_glob)
    roots += _resolve_roots(project_root, cli_roots)
    roots = list(dict.fromkeys(roots))  # de-dupe, preserve order

    log.info("Project root: %s", project_root)
    for r in roots:
        log.info("  scanning: %s%s", r, "" if r.exists() else "  (missing)")

    records, errors = load_semantic_records(
        roots,
        default_scope=args.scope,
        on_error="raise" if args.strict else "warn",
    )
    log.info("Parsed %d semantic record(s); %d error(s)", len(records), len(errors))

    if args.dry_run or not records:
        for r in records:
            log.info(
                "  - %s/%s (kind=%s, name=%s, scope=%s, realized_by=%d, governs=%d)",
                r.scope, r.id, r.kind, r.name, r.scope,
                len(r.realized_by), len(r.governs),
            )
        if errors:
            log.warning("Errors: %d (first: %s)", len(errors), errors[0])
        if args.dry_run:
            return 0
        if not records:
            log.warning("No semantic records found; nothing to write.")
            return 0

    driver = GraphDatabase.driver(
        db_cfg.get("uri", "bolt://127.0.0.1:7687"),
        auth=(db_cfg.get("user", "neo4j"), db_cfg.get("password", "")),
    )
    db_name = db_cfg.get("name") or "neo4j"
    dims = int(emb_cfg.get("dimensions") or 384)

    try:
        with driver.session(database=db_name) as session:
            if args.clear_first:
                clear_semantic_layer(session)

            _ensure_schema(session, dims=dims)

            node_payload = [r.node_props() for r in records]
            write_semantic_nodes(session, node_payload)
            log.info("Wrote %d :Semantic node(s)", len(node_payload))

            related_edges: list[dict] = []
            for r in records:
                for dst in r.related:
                    # Allow "scope:id" or just "id" (defaults to same scope).
                    if ":" in dst:
                        dst_scope, dst_id = dst.split(":", 1)
                    else:
                        dst_scope, dst_id = r.scope, dst
                    related_edges.append({
                        "scope": r.scope,
                        "src_id": r.id,
                        "dst_scope": dst_scope.strip(),
                        "dst_id": dst_id.strip(),
                    })

            realized_edges = [
                {"scope": r.scope, "id": r.id, "qualified_name": q}
                for r in records
                for q in r.realized_by
            ]
            governs_edges = [
                {"scope": r.scope, "id": r.id, "qualified_name": q}
                for r in records
                for q in r.governs
            ]

            if related_edges:
                write_semantic_related(session, related_edges)
                log.info("Wrote %d RELATED_TO edge(s)", len(related_edges))
            if realized_edges:
                wired = write_semantic_realized_by(session, realized_edges)
                log.info(
                    "Wrote %d EMBODIES/EMBODIED_BY edge(s) "
                    "(of %d declared; %d unresolved qualified_names)",
                    wired, len(realized_edges), len(realized_edges) - wired,
                )
            if governs_edges:
                wired = write_semantic_governs(session, governs_edges)
                log.info(
                    "Wrote %d GOVERNED_BY edge(s) "
                    "(of %d declared; %d unresolved qualified_names)",
                    wired, len(governs_edges), len(governs_edges) - wired,
                )
    finally:
        driver.close()

    if errors:
        log.warning("Skipped %d malformed file(s):", len(errors))
        for path, msg in errors:
            log.warning("  %s — %s", path, msg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
