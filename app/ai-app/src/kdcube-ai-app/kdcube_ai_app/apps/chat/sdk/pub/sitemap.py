# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

# chat/sdk/pub/sitemap.py
"""Public-content sitemap generation.

The platform serves one ``sitemap.xml`` per public content alias, listing the
canonical URL and accurate ``lastmod`` of every *published* item from the hot
alias index (retracted items are dropped — their URLs answer 410). Configured
catalogs also receive filtered child sitemaps at
``<alias>/<catalog-prefix>/sitemap.xml`` so a host can submit and monitor one
editorial section independently without maintaining a second content index.

Host-level ``robots.txt`` and the top-level sitemap **index** stay
host/deployment-owned: a site references the per-alias sitemap URLs from its
own index. ``sitemap_descriptor`` is the machine-readable handle a host can
use to build that reference without scraping.
"""
from __future__ import annotations

import html
from typing import Any, Dict, List, Optional

from kdcube_ai_app.apps.chat.sdk.pub.model import (
    PublicContentAliasConfig,
    PublicContentAliasIndex,
    PublicContentCatalogConfig,
    PublicContentIndexEntry,
)


def _esc(value: str) -> str:
    return html.escape(str(value or ""), quote=True)


def render_sitemap_xml(
    index: PublicContentAliasIndex,
    *,
    config: PublicContentAliasConfig,
    fallback_base_url: str = "",
    catalog: Optional[PublicContentCatalogConfig] = None,
) -> str:
    """Render an alias or catalog urlset.

    ``fallback_base_url`` mirrors the render-layer rule: the configured
    ``canonical_base`` wins; otherwise entries resolve against the serving
    route so a local deployment still emits valid URLs. When ``catalog`` is
    provided, only entries covered by that catalog prefix are emitted.
    """
    base = (config.canonical_base or "").rstrip("/") or (fallback_base_url or "").rstrip("/")
    lines: List[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    published = [
        entry
        for entry in index.entries
        if entry.state == "published" and (catalog is None or catalog.covers(entry.slug))
    ]
    # Catalog (fold) pages are canonical browsable URLs of their own; their
    # lastmod is the newest published item under the prefix.
    catalogs = [catalog] if catalog is not None else config.catalogs
    for catalog_entry in catalogs:
        if not base:
            continue
        covered = [e for e in published if catalog_entry.covers(e.slug)]
        lastmod = max((e.lastmod for e in covered if e.lastmod), default="")
        lines.append("  <url>")
        catalog_url = config.canonical_url(catalog_entry.prefix) or base
        lines.append(f"    <loc>{_esc(catalog_url)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{_esc(lastmod)}</lastmod>")
        lines.append("  </url>")
    for entry in published:
        if not base:
            continue
        lines.append("  <url>")
        lines.append(f"    <loc>{_esc(f'{base}/{entry.slug}')}</loc>")
        if entry.lastmod:
            lines.append(f"    <lastmod>{_esc(entry.lastmod)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def _catalog_descriptor(
    *,
    catalog: PublicContentCatalogConfig,
    sitemap_url: str,
    published: List[PublicContentIndexEntry],
) -> Dict[str, Any]:
    covered = [entry for entry in published if catalog.covers(entry.slug)]
    lastmod = max((entry.lastmod for entry in covered if entry.lastmod), default="")
    return {
        "prefix": catalog.prefix,
        "label": catalog.label,
        "sitemap_url": sitemap_url,
        "item_count": len(covered),
        "lastmod": lastmod,
    }


def sitemap_descriptor(
    *,
    config: PublicContentAliasConfig,
    sitemap_url: str,
    index: PublicContentAliasIndex,
) -> Dict[str, Any]:
    """Machine-readable descriptor of one alias sitemap, for host-level
    federation (the host's sitemap index references ``sitemap_url``)."""
    published = [e for e in index.entries if e.state == "published"]
    lastmod = max((e.lastmod for e in published if e.lastmod), default="")
    suffix = "/sitemap.xml"
    alias_base = sitemap_url[: -len(suffix)] if sitemap_url.endswith(suffix) else sitemap_url.rstrip("/")
    catalog_sitemaps = [
        _catalog_descriptor(
            catalog=catalog,
            sitemap_url=f"{alias_base}/{catalog.prefix}/sitemap.xml",
            published=published,
        )
        for catalog in config.catalogs
        if catalog.prefix
    ]
    return {
        "alias": config.alias,
        "sitemap_url": sitemap_url,
        "catalog_sitemaps": catalog_sitemaps,
        "canonical_base": config.canonical_base,
        "item_count": len(published),
        "lastmod": lastmod,
        "generation": index.generation,
    }
