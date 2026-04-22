"""Integration tests that hit the real IPQS API.

Run with:
    uv run pytest -m integration

Requires IPQS_API_KEY in the environment or a .env file.
These tests are skipped in normal test runs unless explicitly selected.
"""
from __future__ import annotations

import os
import pytest

from ipqs_tui.client import IPQSClient, IPQSError


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    key = os.getenv("IPQS_API_KEY")
    if not key:
        pytest.skip("IPQS_API_KEY not set")
    return IPQSClient(api_key=key)


# ---------------------------------------------------------------------------
# IP Lookup
# ---------------------------------------------------------------------------

class TestIPLookupReal:
    def test_google_dns_has_fraud_score(self, client):
        result = client.ip_lookup("8.8.8.8")
        assert result.get("success") is True
        assert isinstance(result.get("fraud_score"), (int, float))

    def test_cloudflare_dns_not_proxy(self, client):
        result = client.ip_lookup("1.1.1.1")
        assert result.get("success") is True
        assert result.get("fraud_score", 100) < 50

    def test_strictness_param_accepted(self, client):
        result = client.ip_lookup("8.8.8.8", strictness="0")
        assert result.get("success") is True


# ---------------------------------------------------------------------------
# Email Verification
# ---------------------------------------------------------------------------

class TestEmailLookupReal:
    def test_gmail_address_valid(self, client):
        result = client.email_lookup("test@gmail.com")
        assert result.get("success") is True
        assert "valid" in result
        assert "fraud_score" in result

    def test_disposable_email_flagged(self, client):
        result = client.email_lookup("throwaway@mailinator.com")
        assert result.get("success") is True
        assert result.get("disposable") is True

    def test_fast_mode_accepted(self, client):
        result = client.email_lookup("test@gmail.com", fast="true")
        assert result.get("success") is True


# ---------------------------------------------------------------------------
# Phone Validation
# ---------------------------------------------------------------------------

class TestPhoneLookupReal:
    def test_us_phone_number(self, client):
        result = client.phone_lookup("+12025551234")
        assert result.get("success") is True
        assert "fraud_score" in result

    def test_international_phone(self, client):
        result = client.phone_lookup("+442071838750")
        assert result.get("success") is True
        assert "country" in result or "fraud_score" in result


# ---------------------------------------------------------------------------
# URL / Domain Lookup
# ---------------------------------------------------------------------------

class TestURLLookupReal:
    def test_google_is_safe(self, client):
        result = client.url_lookup("https://www.google.com")
        assert result.get("success") is True
        assert result.get("unsafe") is False

    def test_example_com_returns_fields(self, client):
        result = client.url_lookup("http://example.com")
        assert result.get("success") is True
        assert "domain" in result or "spamming" in result or "malware" in result

    def test_strictness_param_accepted(self, client):
        result = client.url_lookup("https://example.com", strictness="0")
        assert result.get("success") is True


# ---------------------------------------------------------------------------
# Account / Meta
# ---------------------------------------------------------------------------

class TestCreditUsageReal:
    def test_returns_credit_info(self, client):
        result = client.credit_usage()
        assert result.get("success") is True
        credit_fields = {"credits", "current_credits", "max_credits", "credit_usage"}
        assert credit_fields & set(result.keys()), (
            f"Expected a credit field in response, got: {list(result.keys())}"
        )

class TestCountryListReal:
    def test_returns_list(self, client):
        result = client.country_list()
        assert isinstance(result, (dict, list))