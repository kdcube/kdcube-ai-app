"""
Standalone CALLS-edge extractor.

Use when `mcp__coding-core__index_calls` stalls/times out via MCP for large
codebases. Runs Pyright LSP from this process and writes CALLS edges
directly to Neo4j. Reads creds and target paths from `config.json`.

Run from the repo root:
    python integration/coding-core/index_calls_standalone.py
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from neo4j import GraphDatabase

from extraction.lsp_extractor import extract_calls_via_lsp  # type: ignore  # noqa: E402
from graph.writers import write_calls  # type: ignore  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
log = logging.getLogger("coding-core-calls")


def main() -> int:
    cfg_path = Path(__file__).parent / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))

    db = cfg["database"]
    target = cfg["target"]

    log.info("Targeting %s / %s", db["uri"], db["name"])
    driver = GraphDatabase.driver(db["uri"], auth=(db["user"], db["password"]))

    try:
        with driver.session(database=db["name"]) as s:
            methods = s.run("""
                MATCH (c:Class)-[:CONTAINS_METHOD]->(m:Method)
                WHERE c.file_path IS NOT NULL AND m.line_start IS NOT NULL
                RETURN m.qualified_name AS qualified_name,
                       m.name           AS name,
                       c.file_path      AS file_path,
                       m.line_start     AS line_start
            """).data()
            functions = s.run("""
                MATCH (f:Function)
                WHERE f.file_path IS NOT NULL AND f.line_start IS NOT NULL
                RETURN f.qualified_name AS qualified_name,
                       f.name           AS name,
                       f.file_path      AS file_path,
                       f.line_start     AS line_start
            """).data()

        log.info("Methods to resolve: %d  Functions to resolve: %d", len(methods), len(functions))

        t0 = time.time()
        result = extract_calls_via_lsp(
            target["project_root"],
            target["source_roots"],
            methods,
            functions,
        )
        elapsed = time.time() - t0
        log.info(
            "LSP extraction done in %.1fs: %s",
            elapsed,
            result.get("stats"),
        )

        with driver.session(database=db["name"]) as s:
            write_calls(s, result["calls"])
        log.info("Wrote %d CALLS edges", len(result["calls"]))
    finally:
        driver.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
