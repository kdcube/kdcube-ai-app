from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from kdcube_ai_app.apps.chat.sdk.storage.ai_bundle_storage import AIBundleStorage


def _load_preferences_store_module():
    root = Path(__file__).resolve().parents[1]
    module_path = (
        root
        / "sdk"
        / "examples"
        / "bundles"
        / "versatile@2026-03-31-13-36"
        / "preferences_store.py"
    )
    spec = importlib.util.spec_from_file_location("versatile_preferences_store_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _make_storage(tmp_path: Path) -> AIBundleStorage:
    return AIBundleStorage(
        tenant="demo-tenant",
        project="demo-project",
        ai_bundle_id="versatile@2026-03-31-13-36",
        storage_uri=tmp_path.resolve().as_uri(),
    )


def test_preferences_canvas_save_normalizes_document_and_appends_events(tmp_path):
    prefs = _load_preferences_store_module()
    storage = _make_storage(tmp_path)

    result = prefs.save_preferences_canvas_document(
        storage,
        "user-1",
        document_text=json.dumps(
            {
                "[p]_preferred_name": "Elena",
                "theme": "light",
                "profile": {"likes": ["tea", "books"]},
            }
        ),
    )

    current = prefs.load_current_preferences(storage, "user-1")
    assert result["changed_keys"] == ["preferred_name", "theme", "profile"]
    assert result["removed_keys"] == []
    assert current["preferred_name"]["value"] == "Elena"
    assert current["preferred_name"]["source"] == "preferences_canvas"
    assert current["preferred_name"]["origin"] == "user_canvas"
    assert current["preferred_name"]["updated_at"]
    assert current["theme"]["value"] == "light"
    assert current["profile"]["value"] == {"likes": ["tea", "books"]}

    events = prefs.load_preference_events(storage, "user-1")
    assert [event["key"] for event in events] == ["preferred_name", "theme", "profile"]
    assert all(event["origin"] == "user_canvas" for event in events)
    assert result["path"].endswith("preferences/users/user-1/current.json")


def test_preferences_canvas_document_is_simplified_for_human_editing(tmp_path):
    prefs = _load_preferences_store_module()
    storage = _make_storage(tmp_path)

    prefs.append_preference_event(
        storage,
        "user-1",
        key="[p]_preferred_name",
        value="Elena",
        source="chat",
        origin="auto_capture",
        evidence="call me Elena",
    )
    prefs.append_preference_event(
        storage,
        "user-1",
        key="timezone",
        value="Europe/Berlin",
        source="chat",
        origin="auto_capture",
        evidence="I am in Berlin",
    )

    doc = prefs.build_preferences_canvas_document(storage, "user-1")
    parsed = json.loads(doc["document_text"])
    assert parsed["preferred_name"]["value"] == "Elena"
    assert parsed["preferred_name"]["updated_at"]
    assert parsed["preferred_name"]["origin"] == "auto_capture"
    assert parsed["timezone"]["value"] == "Europe/Berlin"
    assert parsed["timezone"]["updated_at"]
    assert doc["path"].endswith("preferences/users/user-1/current.json")
