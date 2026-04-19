# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
from types import SimpleNamespace

from kdcube_ai_app.apps.utils import logging_config


def test_configure_logging_prefers_runtime_env_log_dir_and_prefix(monkeypatch, tmp_path):
    runtime_log_dir = tmp_path / "runtime-logs"
    monkeypatch.setenv("LOG_DIR", str(runtime_log_dir))
    monkeypatch.setenv("LOG_FILE_PREFIX", "supervisor")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    fake_settings = SimpleNamespace(
        PLATFORM=SimpleNamespace(
            LOG=SimpleNamespace(
                LOG_LEVEL="WARNING",
                LOG_MAX_MB=20,
                LOG_BACKUP_COUNT=10,
                LOG_DIR="/Users/elenaviter/.kdcube/host-log-dir",
                LOG_FILE_PREFIX="host-service",
            )
        )
    )
    monkeypatch.setattr(logging_config, "get_settings", lambda: fake_settings)

    root = logging.getLogger()
    old_handlers = list(root.handlers)
    old_level = root.level

    try:
        logging_config.configure_logging()

        assert runtime_log_dir.exists()
        assert (runtime_log_dir / "supervisor.log").exists()
        assert not (runtime_log_dir / "host-service.log").exists()
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass
        for handler in old_handlers:
            root.addHandler(handler)
        root.setLevel(old_level)
