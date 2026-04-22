"""Unit tests for IPQSTUI app logic — no Textual runtime required."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from ipqs_tui.app import IPQSTUI, _field_id
from ipqs_tui.client import IPQSError
from ipqs_tui.operations import OPERATIONS, OPERATIONS_BY_KEY, FieldDef


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app() -> IPQSTUI:
    """Instantiate IPQSTUI bypassing Textual's App.__init__.

    We store state directly in __dict__ to avoid triggering Textual's reactive
    descriptor, which requires a live App node (hasattr(obj, "_id")).
    """
    app = object.__new__(IPQSTUI)
    app.__dict__["field_inputs"] = {}
    app.__dict__["latest_result"] = None
    # Textual reactive descriptors check hasattr(obj, "id") in both __get__ and __set__.
    app.__dict__["id"] = "test-app"
    # selected_key is a reactive; store its internal value using Textual's naming convention.
    app.__dict__["_reactive_selected_key"] = OPERATIONS[0].key
    return app


def _input(value: str) -> MagicMock:
    m = MagicMock()
    m.value = value
    return m


def _fill_inputs(op, overrides: dict[str, str] | None = None) -> dict[str, MagicMock]:
    overrides = overrides or {}
    return {f.name: _input(overrides.get(f.name, "")) for f in op.fields}


# ---------------------------------------------------------------------------
# _field_label_text
# ---------------------------------------------------------------------------

class TestFieldLabelText:
    def test_required_appends_star(self):
        f = FieldDef("ip", "IP address", required=True)
        assert IPQSTUI._field_label_text(f) == "IP address *"

    def test_optional_no_star(self):
        f = FieldDef("strictness", "Strictness", required=False)
        assert IPQSTUI._field_label_text(f) == "Strictness"

    def test_optional_with_complex_label(self):
        f = FieldDef("ua", "User-Agent string", required=False)
        assert IPQSTUI._field_label_text(f) == "User-Agent string"


# ---------------------------------------------------------------------------
# _collect_kwargs
# ---------------------------------------------------------------------------

class TestCollectKwargs:
    def test_collects_filled_values(self):
        app = _make_app()
        op = OPERATIONS_BY_KEY["ip_lookup"]
        app.field_inputs = _fill_inputs(op, {"ip": "8.8.8.8", "strictness": "2"})
        kwargs = app._collect_kwargs(op)
        assert kwargs["ip"] == "8.8.8.8"
        assert kwargs["strictness"] == "2"

    def test_missing_required_raises(self):
        app = _make_app()
        op = OPERATIONS_BY_KEY["ip_lookup"]
        app.field_inputs = _fill_inputs(op)  # all empty
        with pytest.raises(IPQSError, match="Missing required field"):
            app._collect_kwargs(op)

    def test_empty_optional_excluded(self):
        app = _make_app()
        op = OPERATIONS_BY_KEY["ip_lookup"]
        app.field_inputs = _fill_inputs(op, {"ip": "1.2.3.4"})
        kwargs = app._collect_kwargs(op)
        for v in kwargs.values():
            assert v != ""
        assert "ip" in kwargs

    def test_whitespace_stripped(self):
        app = _make_app()
        op = OPERATIONS_BY_KEY["email_lookup"]
        app.field_inputs = _fill_inputs(op, {"email": "  test@example.com  "})
        kwargs = app._collect_kwargs(op)
        assert kwargs["email"] == "test@example.com"

    def test_whitespace_only_optional_excluded(self):
        app = _make_app()
        op = OPERATIONS_BY_KEY["email_lookup"]
        app.field_inputs = _fill_inputs(op, {"email": "a@b.com", "timeout": "   "})
        kwargs = app._collect_kwargs(op)
        assert "timeout" not in kwargs

    def test_all_optional_filled(self):
        app = _make_app()
        op = OPERATIONS_BY_KEY["email_lookup"]
        app.field_inputs = _fill_inputs(
            op, {"email": "a@b.com", "timeout": "5", "fast": "true", "abuse_strictness": "1"}
        )
        kwargs = app._collect_kwargs(op)
        assert kwargs == {
            "email": "a@b.com",
            "timeout": "5",
            "fast": "true",
            "abuse_strictness": "1",
        }


# ---------------------------------------------------------------------------
# _invoke routing
# ---------------------------------------------------------------------------

class TestInvokeRouting:
    def _method(self):
        return MagicMock(return_value={"success": True})

    def test_ip_lookup(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["ip_lookup"], {"ip": "1.2.3.4", "strictness": "1"})
        m.assert_called_once_with("1.2.3.4", strictness="1")

    def test_email_lookup(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["email_lookup"], {"email": "a@b.com", "fast": "true"})
        m.assert_called_once_with("a@b.com", fast="true")

    def test_phone_lookup(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["phone_lookup"], {"phone": "+15555550123"})
        m.assert_called_once_with("+15555550123")

    def test_url_lookup(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["url_lookup"], {"url": "https://example.com"})
        m.assert_called_once_with("https://example.com")

    def test_device_lookup(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["device_lookup"], {"fingerprint": "fp123"})
        m.assert_called_once_with("fp123")

    def test_leak_password(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["leak_password"], {"password": "secret"})
        m.assert_called_once_with(leak_type="password", payload={"password": "secret"})

    def test_leak_emailpass(self):
        app, m = _make_app(), self._method()
        app._invoke(
            m, OPERATIONS_BY_KEY["leak_emailpass"], {"email": "a@b.com", "password": "pass"}
        )
        m.assert_called_once_with(
            leak_type="emailpass", payload={"email": "a@b.com", "password": "pass"}
        )

    def test_malware_scan(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["malware_scan"], {"file_path": "/tmp/file.exe"})
        m.assert_called_once_with("/tmp/file.exe")

    def test_device_averages(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["device_averages"], {"tracker_id": "t123", "days": "7"})
        m.assert_called_once_with("t123", days="7")

    def test_csv_upload(self):
        app, m = _make_app(), self._method()
        app._invoke(
            m, OPERATIONS_BY_KEY["csv_upload"], {"file_path": "/tmp/data.csv", "type": "email"}
        )
        m.assert_called_once_with("/tmp/data.csv", type="email")

    def test_csv_status(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["csv_status"], {"csv_id": "id123"})
        m.assert_called_once_with("id123")

    def test_download_result(self):
        app, m = _make_app(), self._method()
        app._invoke(
            m,
            OPERATIONS_BY_KEY["download_result"],
            {"url": "https://example.com/dl", "save_to": "/tmp/out.csv"},
        )
        m.assert_called_once_with("https://example.com/dl", "/tmp/out.csv")

    def test_generic_passthrough(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["proxy_averages"], {"days": "7", "strictness": "1"})
        m.assert_called_once_with(days="7", strictness="1")

    def test_credit_usage_no_kwargs(self):
        app, m = _make_app(), self._method()
        app._invoke(m, OPERATIONS_BY_KEY["credit_usage"], {})
        m.assert_called_once_with()


# ---------------------------------------------------------------------------
# _build_operation_options
# ---------------------------------------------------------------------------

class TestBuildOperationOptions:
    def test_first_option_is_separator(self):
        app = _make_app()
        options = app._build_operation_options()
        assert options[0].disabled is True
        assert options[0].id is not None
        assert options[0].id.startswith("sep::")

    def test_separator_count_equals_category_count(self):
        app = _make_app()
        options = app._build_operation_options()
        separators = [o for o in options if o.id and o.id.startswith("sep::")]
        categories = {op.category for op in OPERATIONS}
        assert len(separators) == len(categories)

    def test_operation_option_count(self):
        app = _make_app()
        options = app._build_operation_options()
        ops = [o for o in options if o.id and not o.id.startswith("sep::")]
        assert len(ops) == len(OPERATIONS)

    def test_all_operation_keys_present(self):
        app = _make_app()
        options = app._build_operation_options()
        ids = {o.id for o in options if o.id and not o.id.startswith("sep::")}
        for op in OPERATIONS:
            assert op.key in ids

    def test_separators_not_selectable(self):
        app = _make_app()
        options = app._build_operation_options()
        for o in options:
            if o.id and o.id.startswith("sep::"):
                assert o.disabled is True


# ---------------------------------------------------------------------------
# action_save_result
# ---------------------------------------------------------------------------

class TestActionSaveResult:
    def test_no_result_sets_error(self):
        app = _make_app()
        messages: list[tuple[str, bool]] = []
        app._set_status = lambda msg, *, error=False: messages.append((msg, error))

        app.action_save_result()

        assert messages and messages[0][1] is True

    def test_saves_json_to_disk(self, tmp_path, monkeypatch):
        from unittest.mock import PropertyMock
        app = _make_app()
        app.__dict__["latest_result"] = {"fraud_score": 99, "success": True}
        messages: list[str] = []
        app._set_status = lambda msg, *, error=False: messages.append(msg)

        monkeypatch.chdir(tmp_path)
        # selected_key is a Textual reactive; patch it at class level for this test.
        with patch.object(IPQSTUI, "selected_key", new_callable=PropertyMock, return_value="ip_lookup"):
            app.action_save_result()

        saved_files = list(tmp_path.glob("ipqs-result-ip_lookup-*.json"))
        assert len(saved_files) == 1
        data = json.loads(saved_files[0].read_text())
        assert data["fraud_score"] == 99


# ---------------------------------------------------------------------------
# action_clear_fields
# ---------------------------------------------------------------------------

class TestActionClearFields:
    def test_clears_all_inputs(self):
        app = _make_app()
        inputs = {
            "ip": _input("1.2.3.4"),
            "strictness": _input("2"),
        }
        app.field_inputs = inputs
        messages: list[str] = []
        app._set_status = lambda msg, *, error=False: messages.append(msg)

        app.action_clear_fields()

        for widget in inputs.values():
            assert widget.value == ""
        assert messages

    def test_clear_with_no_fields_is_safe(self):
        app = _make_app()
        app.field_inputs = {}
        messages: list[str] = []
        app._set_status = lambda msg, *, error=False: messages.append(msg)
        app.action_clear_fields()  # must not raise
        assert messages


# ---------------------------------------------------------------------------
# _field_id slug helper
# ---------------------------------------------------------------------------

class TestFieldIdSlug:
    def test_simple_name_passes_through(self):
        assert _field_id("ip") == "field-ip"

    def test_underscore_preserved(self):
        assert _field_id("user_agent") == "field-user_agent"

    def test_brackets_replaced(self):
        assert _field_id("update[ConversionStatus]") == "field-update_ConversionStatus_"

    def test_slash_replaced(self):
        assert _field_id("a/b") == "field-a_b"

    def test_unicode_replaced(self):
        # Non-ASCII letters fall outside [A-Za-z0-9_-] and get replaced.
        slug = _field_id("nãmé")
        assert slug.startswith("field-")
        assert all(c.isascii() and (c.isalnum() or c in "_-") for c in slug)

    def test_leading_digit_handled(self):
        # The slug part itself ('123abc') would start with a digit; the helper
        # prepends an underscore so the *slug* doesn't violate that rule. The
        # final id then becomes 'field-_123abc' which Textual accepts.
        slug = _field_id("123abc")
        assert slug == "field-_123abc"

    def test_all_operation_field_names_produce_valid_ids(self):
        """Every field in every Operation must produce a Textual-valid id."""
        import re
        valid = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
        for op in OPERATIONS:
            for field in op.fields:
                slug = _field_id(field.name)
                assert valid.match(slug), (
                    f"{op.key}.{field.name} → {slug!r} is not a valid Textual id"
                )


# ---------------------------------------------------------------------------
# _set_status — markup safety
# ---------------------------------------------------------------------------

class TestSetStatusMarkup:
    """The status line uses Rich markup. Bare brackets in the message body
    must be escaped, otherwise Rich will eat them or raise on bad markup.
    """

    def _patch_status(self, app):
        captured: list[str] = []
        fake_static = MagicMock()
        fake_static.update = lambda text: captured.append(text)
        app.query_one = MagicMock(return_value=fake_static)
        return captured

    def test_ok_prefix(self):
        app = _make_app()
        captured = self._patch_status(app)
        app._set_status("loaded")
        assert "OK" in captured[0]
        assert "loaded" in captured[0]

    def test_error_prefix(self):
        app = _make_app()
        captured = self._patch_status(app)
        app._set_status("boom", error=True)
        assert "ERROR" in captured[0]
        assert "boom" in captured[0]

    def test_message_with_brackets_is_escaped(self):
        app = _make_app()
        captured = self._patch_status(app)
        # If we naively interpolated '[boom]', Rich would treat it as markup
        # and either drop it or raise MarkupError. Escaping must happen.
        app._set_status("had [boom] inside", error=True)
        assert r"\[boom]" in captured[0]


# ---------------------------------------------------------------------------
# Worker callbacks: _on_request_success / _on_request_error
# ---------------------------------------------------------------------------

class TestWorkerCallbacks:
    def _patched_app(self):
        app = _make_app()
        fake_status = MagicMock()
        fake_pretty = MagicMock()
        # Route query_one based on selector
        def query_one(selector, _type=None):
            if selector == "#status":
                return fake_status
            if selector == "#result":
                return fake_pretty
            raise AssertionError(f"unexpected selector {selector}")
        app.query_one = MagicMock(side_effect=query_one)
        return app, fake_status, fake_pretty

    def test_success_stores_result_and_updates_panes(self):
        app, status, pretty = self._patched_app()
        op = OPERATIONS_BY_KEY["ip_lookup"]
        app._on_request_success(op, {"fraud_score": 0})
        assert app.latest_result == {"fraud_score": 0}
        pretty.update.assert_called_once_with({"fraud_score": 0})
        # Status text contains the OK tag and the operation label
        assert status.update.call_count == 1
        msg = status.update.call_args.args[0]
        assert op.label in msg

    def test_error_stores_error_payload(self):
        app, status, pretty = self._patched_app()
        op = OPERATIONS_BY_KEY["ip_lookup"]
        app._on_request_error(op, IPQSError("nope"))
        assert app.latest_result == {"error": "nope", "operation": op.label}
        pretty.update.assert_called_once_with(app.latest_result)
        assert "ERROR" in status.update.call_args.args[0]


# ---------------------------------------------------------------------------
# action_run_selected dispatch logic (no client / validation failure)
# ---------------------------------------------------------------------------

class TestActionRunDispatch:
    def test_no_client_sets_error_status_and_returns(self):
        app = _make_app()
        app.client = None
        messages: list[tuple[str, bool]] = []
        app._set_status = lambda msg, *, error=False: messages.append((msg, error))
        # If the dispatcher tried to schedule a worker we'd blow up — _make_app
        # isn't a real Textual app — so reaching this line proves we returned.
        app.action_run_selected()
        assert messages == [("Client not initialized. Check IPQS_API_KEY.", True)]

    def test_validation_failure_returns_without_invoking_worker(self):
        from unittest.mock import PropertyMock
        app = _make_app()
        app.client = MagicMock()
        called = []
        app._run_in_worker = lambda *a, **kw: called.append((a, kw))
        messages: list[tuple[str, bool]] = []
        app._set_status = lambda msg, *, error=False: messages.append((msg, error))

        op = OPERATIONS_BY_KEY["ip_lookup"]
        # field_inputs has 'ip' empty → required-field validation fires
        app.field_inputs = _fill_inputs(op)
        with patch.object(IPQSTUI, "selected_key", new_callable=PropertyMock, return_value="ip_lookup"):
            app.action_run_selected()

        assert called == []
        assert messages and messages[0][1] is True
        assert "Missing required field" in messages[0][0]

    def test_validation_success_schedules_worker(self):
        from unittest.mock import PropertyMock
        app = _make_app()
        app.client = MagicMock()
        called = []
        app._run_in_worker = lambda *a, **kw: called.append((a, kw))
        app._set_status = lambda *a, **kw: None

        op = OPERATIONS_BY_KEY["ip_lookup"]
        app.field_inputs = _fill_inputs(op, {"ip": "8.8.8.8"})
        with patch.object(IPQSTUI, "selected_key", new_callable=PropertyMock, return_value="ip_lookup"):
            app.action_run_selected()

        assert len(called) == 1
        sched_args, sched_kwargs = called[0]
        assert sched_args[0] is op
        assert sched_args[1] == {"ip": "8.8.8.8"}