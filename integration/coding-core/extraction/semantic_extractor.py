"""
Semantic-layer markdown extractor.

Reads `*.md` files with YAML frontmatter from configured roots and produces
SemanticRecord objects ready for Neo4j ingestion.

Frontmatter contract (minimum):

    ---
    id: bundle
    kind: concept            # concept | policy | term
    name: Bundle
    aliases: [plugin]        # optional
    category: architectural  # optional
    scope: framework         # optional, defaults to "framework"
    related: [skill, tool]   # optional, list of other Semantic ids
    realized_by:             # optional, qualified_names of code symbols
      - kdcube_ai_app.infra.plugin.bundle_registry.BundleSpec
    governs:                 # optional, qualified_names this policy applies to
      - kdcube_ai_app.apps.chat.sdk.solutions.chatbot.entrypoint.BaseEntrypoint
    rationale: |             # optional, mostly for kind=policy
      ...
    how_to_apply: |          # optional, mostly for kind=policy
      ...
    pitfalls:                # optional, list of strings
      - ...
    ---

    # Display heading (ignored — name comes from frontmatter)

    Long-form definition body. Stored verbatim in `definition`.
"""

from __future__ import annotations

import logging
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

log = logging.getLogger("coding-core-mcp")

VALID_KINDS = {"concept", "policy", "term"}
DEFAULT_SCOPE = "framework"

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<fm>.*?)\n---\s*\n?(?P<body>.*)\Z",
    re.DOTALL,
)


@dataclass
class SemanticRecord:
    id: str
    kind: str
    name: str
    scope: str = DEFAULT_SCOPE
    aliases: list[str] = field(default_factory=list)
    category: str = ""
    summary: str = ""
    definition: str = ""
    rationale: str = ""
    how_to_apply: str = ""
    pitfalls: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    realized_by: list[str] = field(default_factory=list)
    governs: list[str] = field(default_factory=list)
    source: str = "authored"
    source_path: str = ""

    def node_props(self) -> dict[str, Any]:
        """Properties to write onto the :Semantic node (edges handled separately)."""
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "scope": self.scope,
            "aliases": list(self.aliases or []),
            "category": self.category or "",
            "summary": self.summary or "",
            "definition": self.definition or "",
            "rationale": self.rationale or "",
            "how_to_apply": self.how_to_apply or "",
            "pitfalls": list(self.pitfalls or []),
            "source": self.source,
            "source_path": self.source_path,
        }


class SemanticExtractError(ValueError):
    pass


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        out = []
        for item in value:
            if item is None:
                continue
            s = str(item).strip()
            if s:
                out.append(s)
        return out
    raise SemanticExtractError(f"expected list[str], got {type(value).__name__}")


def _derive_summary(body: str) -> str:
    """First non-empty paragraph of the body, stripped of leading heading."""
    if not body:
        return ""
    text = body.strip()
    # Drop a single leading H1 (we already have name from frontmatter).
    if text.startswith("#"):
        first_nl = text.find("\n")
        if first_nl >= 0:
            text = text[first_nl + 1 :].lstrip()
        else:
            text = ""
    # First paragraph = up to first blank line.
    paragraph = text.split("\n\n", 1)[0].strip()
    # Collapse internal whitespace; cap length so summary stays compact.
    paragraph = re.sub(r"\s+", " ", paragraph)
    if len(paragraph) > 400:
        paragraph = paragraph[:397].rstrip() + "…"
    return paragraph


def parse_semantic_file(path: Path, *, default_scope: str = DEFAULT_SCOPE) -> SemanticRecord:
    raw = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise SemanticExtractError(f"missing YAML frontmatter: {path}")

    try:
        meta = yaml.safe_load(match.group("fm")) or {}
    except yaml.YAMLError as exc:
        raise SemanticExtractError(f"invalid YAML frontmatter in {path}: {exc}") from exc
    if not isinstance(meta, dict):
        raise SemanticExtractError(f"frontmatter must be a mapping in {path}")

    body = match.group("body") or ""

    sid = str(meta.get("id") or "").strip()
    kind = str(meta.get("kind") or "").strip().lower()
    name = str(meta.get("name") or "").strip()

    if not sid:
        raise SemanticExtractError(f"`id` is required in {path}")
    if kind not in VALID_KINDS:
        raise SemanticExtractError(
            f"`kind` must be one of {sorted(VALID_KINDS)} in {path}, got {kind!r}"
        )
    if not name:
        raise SemanticExtractError(f"`name` is required in {path}")

    scope = str(meta.get("scope") or default_scope).strip() or default_scope
    summary = str(meta.get("summary") or "").strip() or _derive_summary(body)

    return SemanticRecord(
        id=sid,
        kind=kind,
        name=name,
        scope=scope,
        aliases=_coerce_str_list(meta.get("aliases")),
        category=str(meta.get("category") or "").strip(),
        summary=summary,
        definition=body.strip(),
        rationale=str(meta.get("rationale") or "").strip(),
        how_to_apply=str(meta.get("how_to_apply") or "").strip(),
        pitfalls=_coerce_str_list(meta.get("pitfalls")),
        examples=_coerce_str_list(meta.get("examples")),
        related=_coerce_str_list(meta.get("related")),
        realized_by=_coerce_str_list(meta.get("realized_by")),
        governs=_coerce_str_list(meta.get("governs")),
        source="authored",
        source_path=str(path),
    )


def discover_semantic_files(roots: Iterable[Path]) -> Iterator[Path]:
    seen: set[Path] = set()
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        for md in sorted(root.rglob("*.md")):
            resolved = md.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield md


def load_semantic_records(
    roots: Iterable[Path],
    *,
    default_scope: str = DEFAULT_SCOPE,
    on_error: str = "warn",
) -> tuple[list[SemanticRecord], list[tuple[Path, str]]]:
    """
    Read all `*.md` files under the given roots, return (records, errors).

    `on_error`: "warn" logs and skips; "raise" propagates the first failure.
    """
    records: list[SemanticRecord] = []
    errors: list[tuple[Path, str]] = []
    for path in discover_semantic_files(roots):
        try:
            rec = parse_semantic_file(path, default_scope=default_scope)
        except SemanticExtractError as exc:
            errors.append((path, str(exc)))
            if on_error == "raise":
                raise
            log.warning("[semantic] skip %s: %s", path, exc)
            continue
        records.append(rec)
    return records, errors


__all__ = [
    "SemanticRecord",
    "SemanticExtractError",
    "VALID_KINDS",
    "DEFAULT_SCOPE",
    "parse_semantic_file",
    "discover_semantic_files",
    "load_semantic_records",
]


if __name__ == "__main__":  # pragma: no cover — CLI smoke test
    import json

    if len(sys.argv) < 2:
        print("usage: python -m extraction.semantic_extractor <root> [<root>...]")
        sys.exit(2)
    roots = [Path(p).resolve() for p in sys.argv[1:]]
    records, errors = load_semantic_records(roots)
    out = {
        "records": [asdict(r) for r in records],
        "errors": [{"path": str(p), "error": e} for p, e in errors],
    }
    print(json.dumps(out, indent=2, default=str))
