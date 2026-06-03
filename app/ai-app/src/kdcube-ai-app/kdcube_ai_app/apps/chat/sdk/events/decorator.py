# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Elena Viter

from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping, Sequence
from typing import Any, Callable, TypeVar


EVENT_SOURCE_ATTR = "__kdcube_event_source__"
ARTIFACT_NAMESPACE_REHOSTER_ATTR = "__kdcube_artifact_namespace_rehoster__"

T = TypeVar("T")


@dataclass(frozen=True)
class EventSourceDeclaration:
    """Metadata declared by a tool or non-tool external event source."""

    event_source_id: str
    policies: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    description: str = ""
    version: str = ""
    kind: str = ""
    reactive: bool | None = None
    iteration_credit: int | None = None

    def with_event_source_id(self, event_source_id: str) -> "EventSourceDeclaration":
        return EventSourceDeclaration(
            event_source_id=event_source_id,
            policies=tuple(dict(spec) for spec in self.policies),
            description=self.description,
            version=self.version,
            kind=self.kind,
            reactive=self.reactive,
            iteration_credit=self.iteration_credit,
        )


@dataclass(frozen=True)
class ArtifactNamespaceRehosterDeclaration:
    """Callable metadata for a non-`fi:` artifact namespace.

    A rehoster accepts a domain ref such as `ext:...` and copies the source
    bytes into the ReAct artifact surface, returning normal `fi:`/physical path
    rows that `react.read`, `react.pull`, and `react.checkout` already know how
    to use. The rehoster chooses the destination by artifact meaning: workspace
    state goes to files, story/wizard state goes to snapshots, evidence goes to
    external event attachments, and produced deliverables go to outputs.
    """

    namespace: str
    description: str = ""
    version: str = ""


def event_source_declaration(
    *,
    event_source_id: str,
    policies: Sequence[Mapping[str, Any]] | None = None,
    description: str = "",
    version: str = "",
    kind: str = "",
    reactive: bool | None = None,
    iteration_credit: int | None = None,
) -> EventSourceDeclaration:
    event_source_id = str(event_source_id or "").strip()
    if not event_source_id:
        raise ValueError("event_source_id must be non-empty")
    return EventSourceDeclaration(
        event_source_id=event_source_id,
        policies=_normalize_policy_specs(policies),
        description=str(description or "").strip(),
        version=str(version or "").strip(),
        kind=str(kind or "").strip(),
        reactive=reactive if reactive is None else bool(reactive),
        iteration_credit=_normalize_iteration_credit(iteration_credit),
    )


def artifact_namespace_rehoster_declaration(
    *,
    namespace: str,
    description: str = "",
    version: str = "",
) -> ArtifactNamespaceRehosterDeclaration:
    namespace = str(namespace or "").strip().rstrip(":")
    if not namespace:
        raise ValueError("namespace must be non-empty")
    if any(ch.isspace() for ch in namespace) or "/" in namespace or "\\" in namespace:
        raise ValueError("namespace must be a compact URI-style prefix such as 'ext'")
    return ArtifactNamespaceRehosterDeclaration(
        namespace=namespace,
        description=str(description or "").strip(),
        version=str(version or "").strip(),
    )


def artifact_namespace_rehoster(
    *,
    namespace: str,
    description: str = "",
    version: str = "",
) -> Callable[[T], T]:
    """Mark a callable as a namespace rehoster for ReAct artifact tools.

    The callable is discovered from the same tool/event modules as event
    sources. It is invoked by `react.pull` before the normal `fi:` hydration
    path when a requested ref starts with the registered namespace prefix. The
    returned rows must use the ReAct workspace/artifact layout so downstream
    tools can continue from the returned `logical_path` or `physical_path`.
    """

    declaration = artifact_namespace_rehoster_declaration(
        namespace=namespace,
        description=description,
        version=version,
    )

    def _decorate(obj: T) -> T:
        setattr(obj, ARTIFACT_NAMESPACE_REHOSTER_ATTR, declaration)
        return obj

    return _decorate


def event_source(
    *,
    event_source_id: str,
    policies: Sequence[Mapping[str, Any]] | None = None,
    description: str = "",
    version: str = "",
    kind: str = "",
    reactive: bool | None = None,
    iteration_credit: int | None = None,
) -> Callable[[T], T]:
    """Attach event-source metadata to a tool function or declaration object."""

    declaration = event_source_declaration(
        event_source_id=event_source_id,
        policies=policies,
        description=description,
        version=version,
        kind=kind,
        reactive=reactive,
        iteration_credit=iteration_credit,
    )

    def _decorate(obj: T) -> T:
        setattr(obj, EVENT_SOURCE_ATTR, declaration)
        return obj

    return _decorate


def get_artifact_namespace_rehoster_declaration(obj: Any) -> ArtifactNamespaceRehosterDeclaration | None:
    if obj is None:
        return None
    declaration = getattr(obj, ARTIFACT_NAMESPACE_REHOSTER_ATTR, None)
    if declaration is None and hasattr(obj, "__func__"):
        declaration = getattr(getattr(obj, "__func__", None), ARTIFACT_NAMESPACE_REHOSTER_ATTR, None)
    if isinstance(declaration, ArtifactNamespaceRehosterDeclaration):
        return declaration
    if isinstance(declaration, Mapping):
        try:
            return artifact_namespace_rehoster_declaration(**declaration)
        except Exception:
            return None
    return None


def get_event_source_declaration(obj: Any) -> EventSourceDeclaration | None:
    if obj is None:
        return None
    declaration = getattr(obj, EVENT_SOURCE_ATTR, None)
    if declaration is None and hasattr(obj, "__func__"):
        declaration = getattr(getattr(obj, "__func__", None), EVENT_SOURCE_ATTR, None)
    if isinstance(declaration, EventSourceDeclaration):
        return declaration
    if isinstance(declaration, Mapping):
        try:
            return event_source_declaration(**declaration)
        except Exception:
            return None
    return None


def _normalize_policy_specs(policies: Sequence[Mapping[str, Any]] | None) -> tuple[dict[str, Any], ...]:
    if policies is None:
        return ()
    if isinstance(policies, Mapping) or isinstance(policies, (str, bytes)):
        raise ValueError("policies must be a list of policy binding objects")
    out: list[dict[str, Any]] = []
    for idx, spec in enumerate(policies):
        if not isinstance(spec, Mapping):
            raise ValueError(f"policy binding at index {idx} must be an object")
        react_phase = str(spec.get("react_phase") or "").strip()
        if not react_phase:
            raise ValueError(f"policy binding at index {idx} must define react_phase")
        event_policy_id = str(spec.get("event_policy_id") or "").strip()
        if not event_policy_id:
            raise ValueError(f"policy binding {react_phase!r} must define a non-empty string event_policy_id")
        normalized = dict(spec)
        normalized["react_phase"] = react_phase
        normalized["event_policy_id"] = event_policy_id
        out.append(normalized)
    return tuple(out)


def _normalize_iteration_credit(value: Any) -> int | None:
    if value is None:
        return None
    try:
        credit = int(value)
    except Exception as exc:
        raise ValueError("iteration_credit must be an integer when provided") from exc
    return max(0, credit)
