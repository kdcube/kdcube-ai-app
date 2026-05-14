import asyncio
import sys
import types

import pytest

from kdcube_ai_app.apps.chat.sdk.tools.web import favicon_cache as favicon_cache_module
from kdcube_ai_app.apps.chat.sdk.tools.web.favicon_cache import enrich_sources_pool_with_favicons


class _Log:
    def debug(self, *_args, **_kwargs):
        pass

    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def exception(self, *_args, **_kwargs):
        pass


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_can_be_disabled(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "0")

    rows = [{"url": "https://example.com/article", "title": "Example"}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log())

    assert count == 0
    assert "favicon" not in rows[0]


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_reads_descriptor(monkeypatch, tmp_path):
    monkeypatch.setenv("PLATFORM_DESCRIPTORS_DIR", str(tmp_path))
    monkeypatch.setenv("GATEWAY_COMPONENT", "proc")
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")
    (tmp_path / "assembly.yaml").write_text(
        "platform:\n"
        "  services:\n"
        "    proc:\n"
        "      tools:\n"
        "        web_search:\n"
        "          web_favicon_enrich_enabled: false\n"
    )

    rows = [{"url": "https://example.com/article", "title": "Example"}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log())

    assert count == 0
    assert "favicon" not in rows[0]


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_does_not_start_shared_browser(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")

    class _MinimalPreview:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def _fetch_minimal(self, url):
            assert url == "https://example.com/article"
            return {
                "success": True,
                "favicon": "https://example.com/favicon.ico",
                "title": "Example Title",
            }

    fake_module = types.ModuleType("kdcube_ai_app.infra.rendering.link_preview")

    async def _get_shared_link_preview():
        raise AssertionError("favicon enrichment must not initialize shared browser")

    fake_module.AsyncLinkPreview = _MinimalPreview
    fake_module.get_shared_link_preview = _get_shared_link_preview
    monkeypatch.setitem(sys.modules, "kdcube_ai_app.infra.rendering.link_preview", fake_module)
    monkeypatch.delenv("WEB_FAVICON_ENRICH_TIMEOUT_S", raising=False)

    rows = [{"url": "https://example.com/article", "title": ""}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log())

    assert count == 1
    assert rows[0]["favicon"] == "https://example.com/favicon.ico"
    assert rows[0]["favicon_status"] == "success"
    assert rows[0]["title"] == "Example Title"


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_keeps_partial_success_on_timeout(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")

    class _PartialPreview:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def _fetch_minimal(self, url):
            if url.endswith("/slow"):
                await asyncio.sleep(10)
            return {
                "success": True,
                "favicon": f"{url}/favicon.ico",
                "title": "Fetched",
            }

    fake_module = types.ModuleType("kdcube_ai_app.infra.rendering.link_preview")

    async def _get_shared_link_preview():
        raise AssertionError("favicon enrichment must not initialize shared browser")

    fake_module.AsyncLinkPreview = _PartialPreview
    fake_module.get_shared_link_preview = _get_shared_link_preview
    monkeypatch.setitem(sys.modules, "kdcube_ai_app.infra.rendering.link_preview", fake_module)

    rows = [
        {"url": "https://example.com/fast", "title": "Fast"},
        {"url": "https://slow.example.org/slow", "title": "Slow"},
    ]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log(), timeout_seconds=0.01)

    assert count == 1
    assert rows[0]["favicon"] == "https://example.com/fast/favicon.ico"
    assert rows[0]["favicon_status"] == "success"
    assert "favicon" not in rows[1]
    assert "favicon_status" not in rows[1]


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_falls_back_to_origin_icon(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")

    class _NoMetadataPreview:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def _fetch_minimal(self, url):
            return None

    fake_module = types.ModuleType("kdcube_ai_app.infra.rendering.link_preview")
    fake_module.AsyncLinkPreview = _NoMetadataPreview
    monkeypatch.setitem(sys.modules, "kdcube_ai_app.infra.rendering.link_preview", fake_module)

    async def _fallback(url, *, timeout_seconds):
        return {
            "success": True,
            "favicon": "https://example.com/favicon.ico",
            "title": "example.com",
        }

    monkeypatch.setattr(favicon_cache_module, "_fetch_origin_favicon", _fallback)

    rows = [{"url": "https://example.com/article", "title": ""}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log())

    assert count == 1
    assert rows[0]["favicon"] == "https://example.com/favicon.ico"
    assert rows[0]["favicon_status"] == "success"
    assert rows[0]["title"] == "example.com"


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_uses_bounded_browser_fallback(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")
    monkeypatch.setenv("WEB_FAVICON_BROWSER_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("WEB_FAVICON_BROWSER_FALLBACK_TIMEOUT_S", "0.5")

    closed = False

    class _BrowserPreview:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def _fetch_minimal(self, url):
            return None

        async def _fetch_with_browser(self, url, include_screenshot=False):
            return {
                "success": True,
                "favicon": "https://example.com/browser-icon.ico",
                "title": "Browser",
            }

        async def close(self):
            nonlocal closed
            closed = True

    fake_module = types.ModuleType("kdcube_ai_app.infra.rendering.link_preview")
    fake_module.AsyncLinkPreview = _BrowserPreview
    monkeypatch.setitem(sys.modules, "kdcube_ai_app.infra.rendering.link_preview", fake_module)

    async def _fallback(url, *, timeout_seconds):
        return None

    monkeypatch.setattr(favicon_cache_module, "_fetch_origin_favicon", _fallback)

    rows = [{"url": "https://example.com/article", "title": ""}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log())

    assert count == 1
    assert rows[0]["favicon"] == "https://example.com/browser-icon.ico"
    assert rows[0]["favicon_status"] == "success"
    assert rows[0]["title"] == "Browser"
    assert closed is True


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_browser_fallback_times_out(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")
    monkeypatch.setenv("WEB_FAVICON_BROWSER_FALLBACK_ENABLED", "1")
    monkeypatch.setenv("WEB_FAVICON_BROWSER_FALLBACK_TIMEOUT_S", "0.01")

    class _SlowBrowserPreview:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def _fetch_minimal(self, url):
            return None

        async def _fetch_with_browser(self, url, include_screenshot=False):
            await asyncio.sleep(10)
            return {
                "success": True,
                "favicon": "https://example.com/browser-icon.ico",
            }

        async def close(self):
            pass

    fake_module = types.ModuleType("kdcube_ai_app.infra.rendering.link_preview")
    fake_module.AsyncLinkPreview = _SlowBrowserPreview
    monkeypatch.setitem(sys.modules, "kdcube_ai_app.infra.rendering.link_preview", fake_module)

    async def _fallback(url, *, timeout_seconds):
        return None

    monkeypatch.setattr(favicon_cache_module, "_fetch_origin_favicon", _fallback)

    rows = [{"url": "https://example.com/article", "title": ""}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log())

    assert count == 0
    assert "favicon" not in rows[0]
    assert "favicon_status" not in rows[0]


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_retries_cached_failure(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")

    class _MinimalPreview:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def _fetch_minimal(self, url):
            return {
                "success": True,
                "favicon": "https://example.com/new.ico",
                "title": "Fresh",
            }

    class _Cache:
        def __init__(self):
            self.writes = {}

        async def mget_json(self, keys):
            return [{"success": False, "error": "failed"} for _ in keys]

        async def set_many_json(self, mapping, *, ttl_seconds=None):
            self.writes.update(mapping)
            return len(mapping)

    fake_module = types.ModuleType("kdcube_ai_app.infra.rendering.link_preview")
    fake_module.AsyncLinkPreview = _MinimalPreview
    monkeypatch.setitem(sys.modules, "kdcube_ai_app.infra.rendering.link_preview", fake_module)

    cache = _Cache()
    monkeypatch.setattr(favicon_cache_module, "ensure_namespaced_cache", lambda *_args, **_kwargs: cache)

    rows = [{"url": "https://example.com/article", "title": ""}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log(), cache=object())

    assert count == 1
    assert rows[0]["favicon"] == "https://example.com/new.ico"
    assert rows[0]["favicon_status"] == "success"
    assert rows[0]["title"] == "Fresh"
    assert cache.writes


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_uses_domain_cache_key(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")

    class _Cache:
        def __init__(self):
            self.keys = None

        async def mget_json(self, keys):
            self.keys = list(keys)
            return [{
                "success": True,
                "favicon": "https://example.com/favicon.ico",
                "title": "Example",
            }]

        async def set_many_json(self, mapping, *, ttl_seconds=None):
            raise AssertionError("cache hit must not write")

    cache = _Cache()
    monkeypatch.setattr(favicon_cache_module, "ensure_namespaced_cache", lambda *_args, **_kwargs: cache)

    rows = [
        {"url": "https://example.com/one", "title": ""},
        {"url": "https://example.com/two", "title": ""},
    ]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log(), cache=object())

    assert count == 1
    assert cache.keys == ["favicon:domain:example.com"]
    assert rows[0]["favicon"] == "https://example.com/favicon.ico"
    assert rows[1]["favicon"] == "https://example.com/favicon.ico"


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_honors_negative_cache(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")

    class _Cache:
        async def mget_json(self, keys):
            return [{"success": False, "negative_cache": True, "error": "timeout"}]

        async def set_many_json(self, mapping, *, ttl_seconds=None):
            raise AssertionError("negative cache hit must not write")

    cache = _Cache()
    monkeypatch.setattr(favicon_cache_module, "ensure_namespaced_cache", lambda *_args, **_kwargs: cache)

    rows = [{"url": "https://example.com/article", "title": ""}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log(), cache=object())

    assert count == 1
    assert rows[0]["favicon"] is None
    assert rows[0]["favicon_status"] == "timeout"


@pytest.mark.asyncio
async def test_enrich_sources_pool_with_favicons_writes_failed_domain_with_short_ttl(monkeypatch):
    monkeypatch.setenv("WEB_FAVICON_ENRICH_ENABLED", "1")
    monkeypatch.setenv("WEB_FAVICON_BROWSER_FALLBACK_ENABLED", "0")
    monkeypatch.setenv("WEB_FAVICON_FAILURE_CACHE_TTL_S", "123")

    class _NoMetadataPreview:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def _fetch_minimal(self, url):
            return None

    class _Cache:
        def __init__(self):
            self.writes = []

        async def mget_json(self, keys):
            return [None for _ in keys]

        async def set_many_json(self, mapping, *, ttl_seconds=None):
            self.writes.append((mapping, ttl_seconds))
            return len(mapping)

    fake_module = types.ModuleType("kdcube_ai_app.infra.rendering.link_preview")
    fake_module.AsyncLinkPreview = _NoMetadataPreview
    monkeypatch.setitem(sys.modules, "kdcube_ai_app.infra.rendering.link_preview", fake_module)
    monkeypatch.setattr(favicon_cache_module, "_fetch_origin_favicon", lambda *_args, **_kwargs: None)

    cache = _Cache()
    monkeypatch.setattr(favicon_cache_module, "ensure_namespaced_cache", lambda *_args, **_kwargs: cache)

    rows = [{"url": "https://example.com/article", "title": ""}]
    count = await enrich_sources_pool_with_favicons(rows, log=_Log(), cache=object())

    assert count == 0
    assert cache.writes == [
        ({
            "favicon:domain:example.com": {
                "success": False,
                "negative_cache": True,
                "error": "failed",
            }
        }, 123)
    ]
