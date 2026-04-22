"""End-to-end pilot tests for the IPQSTUI app using Textual's test harness.

These tests run the real composed app against mocked IPQSClient methods.
They exercise mounting, operation switching, button presses, and the async
remove/mount lifecycle that produced the DuplicateIds regression.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ipqs_tui.app import IPQSTUI, _field_id
from ipqs_tui.client import IPQSError
from ipqs_tui.operations import OPERATIONS, OPERATIONS_BY_KEY


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_env(monkeypatch):
    monkeypatch.setenv("IPQS_API_KEY", "pilot-key")
    with patch("ipqs_tui.client.load_dotenv"):
        yield


def _status_text(app: IPQSTUI) -> str:
    """Read the rendered text out of the #status Static widget."""
    return str(app.query_one("#status").render())


def _option_index_for(app: IPQSTUI, key: str) -> int:
    ol = app.query_one("#operations")
    for i in range(ol.option_count):
        opt = ol.get_option_at_index(i)
        if opt.id == key:
            return i
    raise AssertionError(f"option {key!r} not in OptionList")


async def _select_operation(pilot, key: str) -> None:
    """Drive the OptionList to select a specific operation by key."""
    app: IPQSTUI = pilot.app
    ol = app.query_one("#operations")
    ol.highlighted = _option_index_for(app, key)
    ol.action_select()
    await pilot.pause()


# ---------------------------------------------------------------------------
# Initial mount
# ---------------------------------------------------------------------------

class TestInitialMount:
    async def test_default_operation_rendered(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.selected_key == OPERATIONS[0].key
            # First op is ip_lookup → has an 'ip' input mounted
            assert "ip" in app.field_inputs

    async def test_all_operation_fields_rendered(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            op = OPERATIONS_BY_KEY[app.selected_key]
            for field in op.fields:
                assert field.name in app.field_inputs
                # The widget was actually mounted into the DOM
                widget = app.query_one(f"#{_field_id(field.name)}")
                assert widget is app.field_inputs[field.name]

    async def test_status_shows_ok_when_key_loaded(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "OK" in _status_text(app)

    async def test_status_shows_error_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("IPQS_API_KEY", raising=False)
        with patch("ipqs_tui.client.load_dotenv"):
            app = IPQSTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                assert "ERROR" in _status_text(app)
                assert app.client is None


# ---------------------------------------------------------------------------
# Switching operations — regression for DuplicateIds
# ---------------------------------------------------------------------------

class TestOperationSwitching:
    async def test_switch_to_different_op_replaces_fields(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await _select_operation(pilot, "email_lookup")
            assert app.selected_key == "email_lookup"
            assert "email" in app.field_inputs
            assert "ip" not in app.field_inputs  # old field is gone

    async def test_switch_same_key_repeatedly_no_duplicate_ids(self, api_env):
        """Regression: re-selecting the same op used to raise DuplicateIds."""
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            for _ in range(5):
                await _select_operation(pilot, "ip_lookup")
                await _select_operation(pilot, "email_lookup")
            # Should reach here without crashing
            assert app.selected_key == "email_lookup"

    async def test_switch_through_all_operations(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            for op in OPERATIONS:
                await _select_operation(pilot, op.key)
                assert app.selected_key == op.key
                # Each field should be queryable by id
                for field in op.fields:
                    widget = app.query_one(f"#{_field_id(field.name)}")
                    assert widget is not None

    async def test_separator_click_ignored(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            ol = app.query_one("#operations")
            # Option 0 is the first separator
            assert ol.get_option_at_index(0).disabled is True
            starting_key = app.selected_key
            # Separators are disabled; action_select should be a no-op
            ol.highlighted = 0
            ol.action_select()
            await pilot.pause()
            assert app.selected_key == starting_key

    async def test_operation_without_fields_renders_empty(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            await _select_operation(pilot, "credit_usage")
            assert app.field_inputs == {}
            container = app.query_one("#dynamic-form")
            assert len(container.children) == 0


# ---------------------------------------------------------------------------
# Clear button / action
# ---------------------------------------------------------------------------

class TestClearAction:
    async def test_clear_button_empties_fields(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.field_inputs["ip"].value = "8.8.8.8"
            app.field_inputs["strictness"].value = "2"
            await pilot.click("#clear")
            await pilot.pause()
            assert app.field_inputs["ip"].value == ""
            assert app.field_inputs["strictness"].value == ""


# ---------------------------------------------------------------------------
# Run button — worker path
# ---------------------------------------------------------------------------

class TestRunAction:
    async def test_run_missing_required_shows_error(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            # ip is required; leave empty
            app.field_inputs["ip"].value = ""
            await pilot.click("#run")
            await pilot.pause()
            text = _status_text(app)
            assert "ERROR" in text
            assert "Missing required field" in text

    async def test_run_success_updates_result_pane(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.field_inputs["ip"].value = "8.8.8.8"
            app.client.ip_lookup = MagicMock(
                return_value={"success": True, "fraud_score": 0}
            )
            await pilot.click("#run")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.latest_result == {"success": True, "fraud_score": 0}
            assert "completed" in _status_text(app)

    async def test_run_client_error_shown_in_status_and_result(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.field_inputs["ip"].value = "8.8.8.8"
            app.client.ip_lookup = MagicMock(side_effect=IPQSError("upstream down"))
            await pilot.click("#run")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.latest_result == {
                "error": "upstream down",
                "operation": OPERATIONS_BY_KEY["ip_lookup"].label,
            }
            assert "ERROR" in _status_text(app)

    async def test_run_without_client_shows_error(self, monkeypatch):
        monkeypatch.delenv("IPQS_API_KEY", raising=False)
        with patch("ipqs_tui.client.load_dotenv"):
            app = IPQSTUI()
            async with app.run_test() as pilot:
                await pilot.pause()
                # Default op (ip_lookup) is rendered even without a client
                app.field_inputs["ip"].value = "8.8.8.8"
                await pilot.click("#run")
                await pilot.pause()
                assert "Client not initialized" in _status_text(app)


# ---------------------------------------------------------------------------
# Save JSON button
# ---------------------------------------------------------------------------

class TestSaveJsonAction:
    async def test_save_without_result_shows_error(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.latest_result = None
            await pilot.click("#save")
            await pilot.pause()
            assert "ERROR" in _status_text(app)

    async def test_save_writes_latest_result(self, api_env, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.latest_result = {"success": True, "fraud_score": 42}
            await pilot.click("#save")
            await pilot.pause()
            saved = list(Path(tmp_path).glob("ipqs-result-ip_lookup-*.json"))
            assert len(saved) == 1
            data = json.loads(saved[0].read_text())
            assert data == {"fraud_score": 42, "success": True}


# ---------------------------------------------------------------------------
# Keybindings
# ---------------------------------------------------------------------------

class TestKeybindings:
    async def test_ctrl_l_clears_fields(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.field_inputs["ip"].value = "8.8.8.8"
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert app.field_inputs["ip"].value == ""

    async def test_ctrl_r_triggers_run(self, api_env):
        app = IPQSTUI()
        async with app.run_test() as pilot:
            await pilot.pause()
            app.field_inputs["ip"].value = "1.1.1.1"
            app.client.ip_lookup = MagicMock(return_value={"ok": True})
            await pilot.press("ctrl+r")
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert app.latest_result == {"ok": True}
