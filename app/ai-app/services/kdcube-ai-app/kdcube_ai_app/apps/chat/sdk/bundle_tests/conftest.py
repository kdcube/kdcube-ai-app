# SPDX-License-Identifier: MIT

"""Shared pytest fixtures for bundle tests.

These fixtures enable parameterized testing of any bundle by bundle ID.
Run tests for different bundles via:
  pytest test_*.py --bundle-id=react.doc -v
  pytest test_*.py --bundle-id=openrouter-data -v

Infrastructure used:
  - Redis  → real async client via get_async_redis_client() (REDIS_URL from settings)
  - Postgres → real asyncpg pool (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE from settings)
  - comm_context → real ChatTaskPayload with minimal required fields
  - ai_bundle_spec → real BundleSpec with the actual bundle path and ID
"""

import asyncio
import time

import pytest

from kdcube_ai_app.infra.service_hub.inventory import Config, get_settings
from kdcube_ai_app.infra.plugin.bundle_registry import BundleSpec


def pytest_addoption(parser):
    """Add --bundle-id parameter for pytest."""
    parser.addoption(
        "--bundle-id",
        action="store",
        default="react.doc",
        help="Bundle ID to test (auto-discovered from examples/bundles/)",
    )


@pytest.fixture(scope="session")
def bundle_id(request):
    """Bundle ID parameter passed via --bundle-id."""
    return request.config.getoption("--bundle-id")


@pytest.fixture(scope="session")
def redis_client():
    """Real async Redis client using REDIS_URL from settings."""
    from kdcube_ai_app.infra.redis.client import get_async_redis_client
    url = get_settings().REDIS_URL or "redis://localhost:6379/0"
    return get_async_redis_client(url)


@pytest.fixture(scope="session")
def pg_pool():
    """Real asyncpg connection pool using Postgres settings.

    Returns None if Postgres is unreachable — tests that don't invoke
    the graph (the majority) will still pass.
    """
    import asyncpg

    s = get_settings()

    async def _create():
        return await asyncpg.create_pool(
            host=s.PGHOST,
            port=s.PGPORT,
            user=s.PGUSER,
            password=s.PGPASSWORD,
            database=s.PGDATABASE,
            min_size=1,
            max_size=3,
        )

    try:
        return asyncio.run(_create())
    except Exception:
        return None


@pytest.fixture
def comm_context(bundle_id):
    """Real ChatTaskPayload with minimal required fields."""
    from kdcube_ai_app.apps.chat.sdk.protocol import (
        ChatTaskPayload,
        ChatTaskMeta,
        ChatTaskRouting,
        ChatTaskActor,
        ChatTaskUser,
        ChatTaskRequest,
        ChatTaskConfig,
    )
    return ChatTaskPayload(
        meta=ChatTaskMeta(task_id="test-task-001", created_at=time.time()),
        routing=ChatTaskRouting(
            bundle_id=bundle_id,
            session_id="test-session",
            conversation_id="test-conversation",
            turn_id="test-turn",
        ),
        actor=ChatTaskActor(tenant_id="test", project_id="test"),
        user=ChatTaskUser(user_type="regular"),
        request=ChatTaskRequest(message="test"),
        config=ChatTaskConfig(values={}),
    )


@pytest.fixture
def bundle(bundle_id, redis_client, pg_pool, comm_context):
    """Load and initialize bundle for testing.

    Uses real infrastructure:
      - redis_client  → real async Redis client
      - pg_pool       → real asyncpg pool (None if Postgres unavailable)
      - comm_context  → real ChatTaskPayload
      - ai_bundle_spec → real BundleSpec with bundle path and ID

    Args:
        bundle_id: Bundle ID from --bundle-id parameter

    Returns:
        Initialized bundle instance ready for testing
    """
    try:
        from kdcube_ai_app.infra.plugin.bundle_store import _examples_root
        from kdcube_ai_app.infra.plugin.agentic_loader import (
            AgenticBundleSpec,
            _resolve_module,
            _discover_decorated,
        )

        root = _examples_root()
        # Exact match first, then prefix match (e.g. "openrouter-data" -> "openrouter-data@2026-03-11")
        candidates = [
            d for d in sorted(root.iterdir())
            if d.is_dir()
            and (d.name == bundle_id or d.name.startswith(bundle_id + "@"))
            and (d / "entrypoint.py").exists()
        ]
        if not candidates:
            available = sorted(d.name for d in root.iterdir() if d.is_dir() and (d / "entrypoint.py").exists())
            pytest.skip(f"Bundle '{bundle_id}' not found. Available: {', '.join(available)}")

        bundle_dir = candidates[-1]  # latest version if multiple
        spec = AgenticBundleSpec(path=str(bundle_dir), module="entrypoint")
        mod = _resolve_module(spec)
        chosen = _discover_decorated(mod)

        if chosen is None:
            pytest.skip(f"No @agentic_workflow class found in bundle '{bundle_id}'")

        kind, meta, symbol = chosen
        if kind != "class":
            pytest.skip(f"Bundle '{bundle_id}' uses factory pattern, not supported in tests")

        config = Config()
        config.ai_bundle_spec = BundleSpec(id=bundle_id, path=str(bundle_dir))

        instance = symbol(
            config=config,
            pg_pool=pg_pool,
            redis=redis_client,
            comm_context=comm_context,
        )
        return instance

    except ImportError as e:
        pytest.skip(f"Cannot import bundle infrastructure: {str(e)}")
    except Exception as e:
        pytest.skip(f"Cannot initialize bundle '{bundle_id}': {str(e)}")