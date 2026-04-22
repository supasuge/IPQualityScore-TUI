"""Tests for the OPERATIONS data registry."""
from __future__ import annotations

import pytest

from ipqs_tui.client import IPQSClient
from ipqs_tui.operations import OPERATIONS, OPERATIONS_BY_KEY, FieldDef, Operation


class TestOperationsRegistry:
    def test_all_keys_unique(self):
        keys = [op.key for op in OPERATIONS]
        assert len(keys) == len(set(keys)), "Duplicate operation keys found"

    def test_operations_by_key_complete(self):
        for op in OPERATIONS:
            assert op.key in OPERATIONS_BY_KEY
            assert OPERATIONS_BY_KEY[op.key] is op

    def test_all_have_nonempty_description(self):
        for op in OPERATIONS:
            assert op.description.strip(), f"{op.key} has empty description"

    def test_all_have_nonempty_label(self):
        for op in OPERATIONS:
            assert op.label.strip(), f"{op.key} has empty label"

    def test_all_have_nonempty_category(self):
        for op in OPERATIONS:
            assert op.category.strip(), f"{op.key} has empty category"

    def test_all_have_method_name(self):
        for op in OPERATIONS:
            assert op.method_name.strip(), f"{op.key} missing method_name"

    def test_required_fields_have_names(self):
        for op in OPERATIONS:
            for field in op.fields:
                if field.required:
                    assert field.name.strip(), f"required field in {op.key} has empty name"

    def test_leak_ops_static_kwargs(self):
        assert OPERATIONS_BY_KEY["leak_password"].static_kwargs["leak_type"] == "password"
        assert OPERATIONS_BY_KEY["leak_emailpass"].static_kwargs["leak_type"] == "emailpass"

    def test_secret_fields_are_passwords(self):
        for op in OPERATIONS:
            for field in op.fields:
                if field.secret:
                    assert "password" in field.name.lower(), (
                        f"Secret field '{field.name}' in {op.key} does not appear to be a password"
                    )

    def test_known_categories_present(self):
        categories = {op.category for op in OPERATIONS}
        for expected in ("Realtime Lookups", "Account / Meta", "Bulk CSV", "Allowlist / Blocklist"):
            assert expected in categories

    def test_realtime_lookups_have_required_primary_field(self):
        primary_fields = {
            "ip_lookup": "ip",
            "email_lookup": "email",
            "phone_lookup": "phone",
            "url_lookup": "url",
            "device_lookup": "fingerprint",
        }
        for key, field_name in primary_fields.items():
            op = OPERATIONS_BY_KEY[key]
            required = {f.name for f in op.fields if f.required}
            assert field_name in required, f"{key} missing required field '{field_name}'"


class TestFieldDef:
    def test_defaults(self):
        f = FieldDef(name="x", label="X")
        assert f.required is False
        assert f.placeholder == ""
        assert f.default == ""
        assert f.secret is False

    def test_explicit_values(self):
        f = FieldDef("pw", "Password", required=True, placeholder="***", default="", secret=True)
        assert f.required is True
        assert f.secret is True
        assert f.placeholder == "***"

    def test_slots_no_extra_attrs(self):
        f = FieldDef("n", "L")
        with pytest.raises(AttributeError):
            f.nonexistent = "boom"  # type: ignore[attr-defined]


class TestOperation:
    def test_defaults(self):
        op = Operation(key="k", category="c", label="l", method_name="m", description="d")
        assert op.fields == []
        assert op.static_kwargs == {}

    def test_slots_no_extra_attrs(self):
        op = Operation(key="k", category="c", label="l", method_name="m", description="d")
        with pytest.raises(AttributeError):
            op.nonexistent = "boom"  # type: ignore[attr-defined]


class TestOperationClientWiring:
    """Every Operation.method_name must point to a real IPQSClient method."""

    def test_method_names_exist(self):
        for op in OPERATIONS:
            assert hasattr(IPQSClient, op.method_name), (
                f"{op.key}: client has no method {op.method_name!r}"
            )
            assert callable(getattr(IPQSClient, op.method_name))

    def test_field_names_unique_per_operation(self):
        for op in OPERATIONS:
            names = [f.name for f in op.fields]
            assert len(names) == len(set(names)), f"{op.key} has duplicate field names"

    def test_default_values_are_strings(self):
        for op in OPERATIONS:
            for f in op.fields:
                assert isinstance(f.default, str), f"{op.key}.{f.name} default not str"
                assert isinstance(f.placeholder, str), (
                    f"{op.key}.{f.name} placeholder not str"
                )

    def test_leak_ops_share_the_underlying_method(self):
        # Both leak ops dispatch through leaked_lookup with different leak_type.
        assert OPERATIONS_BY_KEY["leak_password"].method_name == "leaked_lookup"
        assert OPERATIONS_BY_KEY["leak_emailpass"].method_name == "leaked_lookup"

    def test_categories_preserve_grouping(self):
        """Operations within the same category should appear contiguously,
        which is what _build_operation_options assumes when emitting separators."""
        seen: dict[str, int] = {}
        for i, op in enumerate(OPERATIONS):
            if op.category in seen and seen[op.category] != i - 1:
                # Allow re-encountering only if the previous index was also same category
                pass  # pragma: no cover
            seen[op.category] = i
        # Reconstruct the run-length encoding and ensure each category appears
        # in only one contiguous block.
        block_starts: dict[str, int] = {}
        prev_cat = None
        block_idx = 0
        for op in OPERATIONS:
            if op.category != prev_cat:
                if op.category in block_starts:
                    raise AssertionError(
                        f"category {op.category!r} appears in multiple non-adjacent blocks"
                    )
                block_starts[op.category] = block_idx
                block_idx += 1
                prev_cat = op.category
