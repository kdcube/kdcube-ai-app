# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Elena Viter

# chat/sdk/tools/web/favicon_cache.py

from __future__ import annotations

import asyncio
import os
from typing import Any, Dict, List, Optional

from kdcube_ai_app.apps.chat.sdk.config_scopes import _load_assembly_plain
from kdcube_ai_app.infra.service_hub.cache import ensure_namespaced_cache
from kdcube_ai_app.infra.namespaces import REDIS
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_UTM_PARAMS = {"utm_source", "utm_medium", "utm_campaign","utm_term","utm_content","utm_id","gclid","fbclid"}


def normalize_url(u: str) -> str:
    try:
        if not u:
            return ""
        s = urlsplit(u.strip())
        scheme = (s.scheme or "https").lower()
        netloc = s.netloc.lower().rstrip(":80").rstrip(":443")
        path = s.path or "/"
        fragment = ""
        q = [(k, v) for k, v in parse_qsl(s.query, keep_blank_values=True) if k.lower() not in _UTM_PARAMS]
        query = urlencode(q, doseq=True)
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return urlunsplit((scheme, netloc, path, query, fragment))
    except Exception:
        return (u or "").strip()


def _favicon_cache_key(url: str) -> str:
    domain = _favicon_cache_domain(url)
    if not domain:
        return ""
    return f"favicon:domain:{domain}"


def _favicon_cache_domain(url: str) -> str:
    try:
        if not url:
            return ""
        parsed = urlsplit(url.strip())
        return (parsed.hostname or "").lower().strip(".")
    except Exception:
        return ""


def _origin_favicon_url(url: str) -> Optional[str]:
    try:
        parsed = urlsplit(url)
        if not parsed.netloc:
            return None
        scheme = (parsed.scheme or "https").lower()
        return f"{scheme}://{parsed.netloc}/favicon.ico"
    except Exception:
        return None


def _response_can_be_favicon(headers: Any) -> bool:
    content_type = (headers.get("content-type") or "").lower()
    if not content_type:
        return True
    if "image/" in content_type or "icon" in content_type:
        return True
    return "application/octet-stream" in content_type


async def _fetch_origin_favicon(url: str, *, timeout_seconds: float) -> Optional[dict]:
    favicon = _origin_favicon_url(url)
    if not favicon:
        return None

    try:
        import aiohttp
    except ImportError:
        return None

    parsed = urlsplit(url)
    timeout = aiohttp.ClientTimeout(total=max(0.2, float(timeout_seconds or 1.0)))
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with aiohttp.ClientSession() as session:
            for method in ("HEAD", "GET"):
                try:
                    async with session.request(
                        method,
                        favicon,
                        timeout=timeout,
                        headers=headers,
                        allow_redirects=True,
                    ) as response:
                        if 200 <= response.status < 400 and _response_can_be_favicon(response.headers):
                            return {
                                "url": url,
                                "domain": parsed.netloc,
                                "title": parsed.netloc,
                                "favicon": str(response.url),
                                "site_name": parsed.netloc,
                                "success": True,
                                "method": "origin_favicon",
                            }
                except Exception:
                    continue
    except Exception:
        return None
    return None


async def _fetch_browser_favicon(preview: Any, url: str, *, timeout_seconds: float) -> Optional[dict]:
    try:
        result = await asyncio.wait_for(
            preview._fetch_with_browser(url, include_screenshot=False),
            timeout=max(0.2, float(timeout_seconds or 1.0)),
        )
    except Exception:
        return None

    if not isinstance(result, dict) or not result.get("success") or not result.get("favicon"):
        return None
    return result


def _component_name() -> str:
    return (os.environ.get("GATEWAY_COMPONENT") or "proc").strip().lower() or "proc"


def _web_search_setting(name: str) -> Any:
    component = _component_name()
    value = _load_assembly_plain(f"platform.services.{component}.tools.web_search.{name}")
    if value is None and component != "proc":
        value = _load_assembly_plain(f"platform.services.proc.tools.web_search.{name}")
    return value


def _setting_bool(*, descriptor_name: str, env_name: str, default: bool) -> bool:
    value = _web_search_setting(descriptor_name)
    if value is None:
        value = os.environ.get(env_name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _setting_float(*, descriptor_name: str, env_name: str, default: float) -> float:
    value = _web_search_setting(descriptor_name)
    if value is None:
        value = os.environ.get(env_name)
    try:
        return float(value)
    except Exception:
        return default


async def enrich_sources_pool_with_favicons(
        sources_pool: List[Dict[str, Any]],
        log,
        *,
        cache: Any = None,
        cache_ttl_seconds: Optional[int] = None,
        timeout_seconds: Optional[float] = None,
) -> int:
    """
    Enrich sources_pool with favicons in-place (FAST batch operation).

    - Uses cheap HTTP metadata first
    - Falls back to origin /favicon.ico when protected article pages block metadata
    - Optionally uses a bounded own-browser fallback for remaining misses
    - Only processes sources without existing 'favicon' key (idempotent)
    - Updates sources_pool list in-place
    - Returns count of newly enriched sources
    """
    if not sources_pool:
        return 0

    enabled = _setting_bool(
        descriptor_name="web_favicon_enrich_enabled",
        env_name="WEB_FAVICON_ENRICH_ENABLED",
        default=True,
    )
    if not enabled:
        log.info("enrich_favicons: disabled")
        return 0

    # Find sources that need enrichment
    to_enrich = []
    url_to_sources: Dict[str, List[Dict[str, Any]]] = {}

    for src in sources_pool:
        if not isinstance(src, dict):
            continue
        if "favicon" in src:  # Already enriched
            continue
        url = (src.get("url") or "").strip()
        if url and (url.startswith("http://") or url.startswith("https://")):
            to_enrich.append(url)
            url_to_sources.setdefault(url, []).append(src)

    if not to_enrich:
        log.debug("enrich_favicons: all sources already enriched")
        return 0

    cache_key_to_url: Dict[str, str] = {}
    cache_key_to_sources: Dict[str, List[Dict[str, Any]]] = {}
    url_to_cache_key: Dict[str, str] = {}
    for url in to_enrich:
        cache_key = _favicon_cache_key(url)
        if not cache_key:
            continue
        cache_key_to_url.setdefault(cache_key, url)
        cache_key_to_sources.setdefault(cache_key, []).extend(url_to_sources.get(url) or [])
        url_to_cache_key[url] = cache_key

    cached_results: Dict[str, Dict[str, Any]] = {}
    if cache is not None:
        try:
            # settings = get_settings()
            cache = ensure_namespaced_cache(
                cache,
                namespace=REDIS.CACHE.FAVICON,
                # tenant=settings.TENANT,
                # project=settings.PROJECT,
                default_ttl_seconds=cache_ttl_seconds,
                use_tp_prefix=False
            )
        except Exception:
            cache = None
    if cache is not None:
        cache_keys = list(cache_key_to_url.keys())
        if cache_keys:
            cached_list = await cache.mget_json(cache_keys)
            for cache_key, cached in zip(cache_keys, cached_list):
                if isinstance(cached, dict):
                    cached_results[cache_key] = cached

    if cached_results:
        for cache_key, cached in cached_results.items():
            sources = cache_key_to_sources.get(cache_key) or []
            if cached.get("success"):
                for src in sources:
                    src["favicon"] = cached.get("favicon")
                    src["favicon_status"] = "success"
                    if not src.get("title") and cached.get("title"):
                        src["title"] = cached["title"]
                continue
            if cached.get("negative_cache"):
                for src in sources:
                    src["favicon"] = None
                    src["favicon_status"] = cached.get("error", "failed")

        to_enrich = [
            url for url in to_enrich
            if not (
                (cached_results.get(url_to_cache_key.get(url, "")) or {}).get("success")
                or (cached_results.get(url_to_cache_key.get(url, "")) or {}).get("negative_cache")
            )
        ]
        if not to_enrich:
            log.debug("enrich_favicons: cache hit for all sources")
            return len(cached_results)

    log.info(f"enrich_favicons: batch enriching {len(to_enrich)}/{len(sources_pool)} sources")
    if timeout_seconds is None:
        timeout_seconds = _setting_float(
            descriptor_name="web_favicon_enrich_timeout_s",
            env_name="WEB_FAVICON_ENRICH_TIMEOUT_S",
            default=3.0,
        )

    # Import the preview implementation directly. Favicon enrichment must not
    # initialize the shared browser service in short-lived tool subprocesses.
    # Browser fallback, when enabled, is own-instance and bounded below.
    try:
        from kdcube_ai_app.infra.rendering.link_preview import AsyncLinkPreview
    except ImportError:
        log.warning("enrich_favicons: link_preview module not available, skipping")
        return 0

    try:
        preview = AsyncLinkPreview(timeout=max(1, int((timeout_seconds or 3.0) * 1000)))

        browser_fallback_enabled = _setting_bool(
            descriptor_name="web_favicon_browser_fallback_enabled",
            env_name="WEB_FAVICON_BROWSER_FALLBACK_ENABLED",
            default=True,
        )
        browser_timeout_seconds = _setting_float(
            descriptor_name="web_favicon_browser_fallback_timeout_s",
            env_name="WEB_FAVICON_BROWSER_FALLBACK_TIMEOUT_S",
            default=2.0,
        )
        failure_cache_ttl_seconds = int(_setting_float(
            descriptor_name="web_favicon_failure_cache_ttl_s",
            env_name="WEB_FAVICON_FAILURE_CACHE_TTL_S",
            default=300.0,
        ))

        # Launch per-URL HTTP-only metadata fetches and keep partial successes.
        to_enrich_set = set(to_enrich)
        fetch_keys = [
            cache_key for cache_key, url in cache_key_to_url.items()
            if url in to_enrich_set
        ]
        unique_urls = [cache_key_to_url[cache_key] for cache_key in fetch_keys]

        async def _fetch_one(url: str) -> tuple[str, Optional[dict], Optional[str]]:
            try:
                result = await asyncio.wait_for(preview._fetch_minimal(url), timeout=timeout_seconds)
                if isinstance(result, dict) and result.get("success") and result.get("favicon"):
                    return url, result, None
                fallback = await _fetch_origin_favicon(url, timeout_seconds=timeout_seconds or 1.0)
                if isinstance(fallback, dict):
                    return url, fallback, None
                return url, None, "failed"
            except asyncio.TimeoutError:
                return url, None, "timeout"
            except Exception as exc:
                return url, None, str(exc) or "failed"

        tasks = [asyncio.create_task(_fetch_one(url)) for url in unique_urls]
        done, pending = await asyncio.wait(tasks, timeout=timeout_seconds)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        results_map: Dict[str, dict] = {}
        browser_candidates: List[str] = []
        failed_count = 0
        timeout_count = len(pending)
        for task in done:
            try:
                url, result, error = task.result()
            except asyncio.CancelledError:
                timeout_count += 1
                continue
            except Exception:
                failed_count += 1
                continue
            if error == "timeout":
                timeout_count += 1
                continue
            if error or not isinstance(result, dict):
                failed_count += 1
                if url:
                    browser_candidates.append(url)
                continue
            if result.get("success") and result.get("favicon"):
                results_map[url] = result
            else:
                failed_count += 1
                if url:
                    browser_candidates.append(url)

        if browser_fallback_enabled and browser_candidates and browser_timeout_seconds > 0:
            browser_deadline = asyncio.get_running_loop().time() + browser_timeout_seconds
            browser_preview = AsyncLinkPreview(timeout=max(1, int(browser_timeout_seconds * 1000)))
            browser_attempted = 0
            try:
                for url in browser_candidates:
                    remaining = browser_deadline - asyncio.get_running_loop().time()
                    if remaining <= 0:
                        break
                    browser_attempted += 1
                    result = await _fetch_browser_favicon(
                        browser_preview,
                        url,
                        timeout_seconds=min(browser_timeout_seconds, remaining),
                    )
                    if isinstance(result, dict):
                        results_map[url] = result
            finally:
                close = getattr(browser_preview, "close", None)
                if close is not None:
                    try:
                        await asyncio.wait_for(close(), timeout=0.5)
                    except Exception:
                        pass
            if browser_attempted:
                recovered_count = sum(1 for url in browser_candidates if url in results_map)
                failed_count = max(0, failed_count - recovered_count)

        # Update sources in-place
        enriched_count = 0
        cache_payload: Dict[str, Dict[str, Any]] = {}
        success_keys = set()
        for url, result in results_map.items():
            cache_key = url_to_cache_key.get(url) or _favicon_cache_key(url)
            sources = cache_key_to_sources.get(cache_key) or url_to_sources.get(url) or []
            if not sources:
                continue
            success_keys.add(cache_key)

            for src in sources:
                src["favicon"] = result.get("favicon")
                src["favicon_status"] = "success"
                # Optionally improve title
                if not src.get("title") and result.get("title"):
                    src["title"] = result["title"]
                enriched_count += 1

            if cache_key:
                cache_payload[cache_key] = {
                    "success": True,
                    "favicon": result.get("favicon"),
                    "title": result.get("title"),
                    "error": None,
                }

        if cache is not None and cache_payload:
            await cache.set_many_json(cache_payload, ttl_seconds=cache_ttl_seconds)

        failed_payload: Dict[str, Dict[str, Any]] = {}
        for cache_key in fetch_keys:
            if cache_key in success_keys:
                continue
            failed_payload[cache_key] = {
                "success": False,
                "negative_cache": True,
                "error": "failed",
            }
        if cache is not None and failed_payload and failure_cache_ttl_seconds > 0:
            await cache.set_many_json(failed_payload, ttl_seconds=failure_cache_ttl_seconds)

        log.info(
            "enrich_favicons: completed %s/%s successful; failed=%s timeout=%s",
            enriched_count,
            len(to_enrich),
            failed_count,
            timeout_count,
        )
        return enriched_count

    except asyncio.TimeoutError:
        log.warning(
            "enrich_favicons: timed out after %.1fs; continuing with fetched favicons only",
            timeout_seconds or 0,
        )
        return 0
    except Exception:
        log.exception("enrich_favicons: failed")
        return 0
