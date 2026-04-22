"""Unit tests for IPQSClient — all HTTP calls are mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from ipqs_tui.client import IPQSClient, IPQSError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_json_response(data: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {"content-type": "application/json"}
    resp.json.return_value = data
    resp.text = json.dumps(data)
    resp.content = json.dumps(data).encode()
    resp.raise_for_status = MagicMock()
    return resp


def _mock_text_response(text: str, content_type: str = "text/plain") -> MagicMock:
    resp = MagicMock()
    resp.headers = {"content-type": content_type}
    resp.text = text
    resp.content = text.encode()
    resp.json.side_effect = ValueError("not json")
    resp.raise_for_status = MagicMock()
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("IPQS_API_KEY", "testkey123")
    with patch("ipqs_tui.client.load_dotenv"):
        return IPQSClient()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestInit:
    def test_reads_key_from_env(self, monkeypatch):
        monkeypatch.setenv("IPQS_API_KEY", "envkey")
        with patch("ipqs_tui.client.load_dotenv"):
            c = IPQSClient()
        assert c.api_key == "envkey"

    def test_explicit_key_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("IPQS_API_KEY", "envkey")
        with patch("ipqs_tui.client.load_dotenv"):
            c = IPQSClient(api_key="explicit")
        assert c.api_key == "explicit"

    def test_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("IPQS_API_KEY", raising=False)
        with patch("ipqs_tui.client.load_dotenv"):
            with pytest.raises(IPQSError, match="Missing IPQS_API_KEY"):
                IPQSClient()

    def test_default_timeout(self, client):
        assert client.timeout == 30.0

    def test_custom_timeout(self, monkeypatch):
        monkeypatch.setenv("IPQS_API_KEY", "k")
        with patch("ipqs_tui.client.load_dotenv"):
            c = IPQSClient(timeout=5.0)
        assert c.timeout == 5.0

    def test_session_headers_set(self, client):
        assert "ipqs-textual-tui" in client.session.headers.get("User-Agent", "")
        assert client.session.headers.get("Accept") == "application/json"


# ---------------------------------------------------------------------------
# _request internals
# ---------------------------------------------------------------------------

class TestRequest:
    def test_builds_correct_url(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("GET", "/json/test/path")
        url = client.session.request.call_args.kwargs["url"]
        assert url == "https://www.ipqualityscore.com/api/json/test/path"

    def test_strips_leading_slash_from_path(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("GET", "json/noslash")
        url = client.session.request.call_args.kwargs["url"]
        assert url == "https://www.ipqualityscore.com/api/json/noslash"

    def test_filters_none_params(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("GET", "/test", params={"a": "val", "b": None, "c": ""})
        params = client.session.request.call_args.kwargs["params"]
        assert params == {"a": "val"}

    def test_post_sends_json_body(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("POST", "/test", json_body={"key": "val"})
        kw = client.session.request.call_args.kwargs
        assert kw["method"] == "POST"
        assert kw["json"] == {"key": "val"}

    def test_extra_headers_forwarded(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("GET", "/test", extra_headers={"X-Custom": "abc"})
        headers = client.session.request.call_args.kwargs["headers"]
        assert headers["X-Custom"] == "abc"

    def test_raises_on_http_error(self, client):
        resp = MagicMock()
        resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        client.session.request = MagicMock(return_value=resp)
        with pytest.raises(requests.HTTPError):
            client._request("GET", "/bad")

    def test_raises_on_api_error(self, client):
        resp = _mock_json_response({"success": False, "message": "invalid key"})
        client.session.request = MagicMock(return_value=resp)
        with pytest.raises(IPQSError, match="invalid key"):
            client._request("GET", "/test")

    def test_raises_on_errors_key(self, client):
        resp = _mock_json_response({"success": True, "errors": ["ip not found"]})
        client.session.request = MagicMock(return_value=resp)
        with pytest.raises(IPQSError, match="ip not found"):
            client._request("GET", "/test")

    def test_non_json_returns_text_dict(self, client):
        resp = _mock_text_response("OK processed")
        client.session.request = MagicMock(return_value=resp)
        result = client._request("GET", "/test")
        assert result == {"success": True, "text": "OK processed"}

    def test_save_to_writes_bytes(self, client, tmp_path):
        save_path = str(tmp_path / "result.csv")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.headers = {"content-type": "text/csv"}
        resp.text = ""
        resp.content = b"col1,col2\n1,2\n"
        client.session.request = MagicMock(return_value=resp)
        result = client._request("GET", "/test", save_to=save_path)
        assert result["success"] is True
        assert result["saved_to"] == save_path
        assert result["size_bytes"] == 14
        assert Path(save_path).read_bytes() == b"col1,col2\n1,2\n"

    def test_save_to_creates_parent_dirs(self, client, tmp_path):
        save_path = str(tmp_path / "deep" / "dir" / "out.bin")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.headers = {"content-type": "application/octet-stream"}
        resp.text = ""
        resp.content = b"\x00\x01\x02"
        client.session.request = MagicMock(return_value=resp)
        client._request("GET", "/test", save_to=save_path)
        assert Path(save_path).exists()


# ---------------------------------------------------------------------------
# _raise_for_api_errors
# ---------------------------------------------------------------------------

class TestRaiseForApiErrors:
    def test_passthrough_on_success(self):
        IPQSClient._raise_for_api_errors({"success": True, "fraud_score": 10})

    def test_raises_on_success_false(self):
        with pytest.raises(IPQSError, match="invalid"):
            IPQSClient._raise_for_api_errors({"success": False, "message": "invalid"})

    def test_raises_on_errors_list(self):
        with pytest.raises(IPQSError, match="bad value"):
            IPQSClient._raise_for_api_errors({"success": True, "errors": ["bad value"]})

    def test_non_dict_passthrough(self):
        IPQSClient._raise_for_api_errors([1, 2, 3])
        IPQSClient._raise_for_api_errors("plain string")
        IPQSClient._raise_for_api_errors(None)


# ---------------------------------------------------------------------------
# URL construction for each lookup method
# ---------------------------------------------------------------------------

class TestLookupURLs:
    """Each method must embed the key and the (URL-encoded) primary argument."""

    def _get_url(self, client, fn, *args, **kwargs) -> str:
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        fn(*args, **kwargs)
        return client.session.request.call_args.kwargs["url"]

    def test_ip_lookup(self, client):
        url = self._get_url(client, client.ip_lookup, "1.2.3.4")
        assert url == "https://www.ipqualityscore.com/api/json/ip/testkey123/1.2.3.4"

    def test_email_lookup_percent_encodes(self, client):
        url = self._get_url(client, client.email_lookup, "user+tag@example.com")
        assert "testkey123" in url
        assert "user%2Btag%40example.com" in url

    def test_phone_lookup_percent_encodes(self, client):
        url = self._get_url(client, client.phone_lookup, "+15555550123")
        assert "%2B15555550123" in url

    def test_url_lookup_percent_encodes(self, client):
        url = self._get_url(client, client.url_lookup, "https://bad.example.com/path?q=1")
        assert "testkey123" in url
        assert "https%3A" in url

    def test_device_lookup(self, client):
        url = self._get_url(client, client.device_lookup, "fp_abc123")
        assert url.endswith("/fp_abc123")

    def test_leaked_lookup_is_post_with_json(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client.leaked_lookup("password", {"password": "secret"})
        kw = client.session.request.call_args.kwargs
        assert kw["method"] == "POST"
        assert "leaked/password" in kw["url"]
        assert kw["json"] == {"password": "secret"}

    def test_bulk_csv_status_url(self, client):
        url = self._get_url(client, client.bulk_csv_status, "csv-id-xyz")
        assert "csv-id-xyz" in url

    def test_credit_usage_url(self, client):
        url = self._get_url(client, client.credit_usage)
        assert "account/testkey123" in url

    def test_country_list_url(self, client):
        url = self._get_url(client, client.country_list)
        assert url.endswith("/country/list")

    def test_allowlist_create_is_post(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client.allowlist_create(value="1.2.3.4", value_type="ip", type="proxy")
        assert client.session.request.call_args.kwargs["method"] == "POST"

    def test_blocklist_create_is_post(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client.blocklist_create(value="bad@example.com", value_type="email", type="email")
        assert client.session.request.call_args.kwargs["method"] == "POST"


# ---------------------------------------------------------------------------
# File-based operations
# ---------------------------------------------------------------------------

class TestFileOperations:
    def test_malware_scan_raises_if_file_missing(self, client):
        with pytest.raises(IPQSError, match="File not found"):
            client.malware_file_scan("/nonexistent/file.exe")

    def test_malware_scan_uploads_file(self, client, tmp_path):
        sample = tmp_path / "sample.txt"
        sample.write_bytes(b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE")
        resp = _mock_json_response({"success": True, "safe": True})
        client.session.request = MagicMock(return_value=resp)
        result = client.malware_file_scan(str(sample))
        assert result["success"] is True
        kw = client.session.request.call_args.kwargs
        assert "malware" in kw["url"]
        assert "file" in kw["files"]

    def test_csv_upload_raises_if_file_missing(self, client):
        with pytest.raises(IPQSError, match="CSV file not found"):
            client.bulk_csv_upload("/nonexistent/data.csv")

    def test_csv_upload_posts_file(self, client, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("email\ntest@example.com\n")
        resp = _mock_json_response({"success": True, "id": "job-1"})
        client.session.request = MagicMock(return_value=resp)
        result = client.bulk_csv_upload(str(csv_file))
        assert result["success"] is True
        assert "file" in client.session.request.call_args.kwargs["files"]

    def test_download_result_saves_bytes(self, client, tmp_path):
        save_path = str(tmp_path / "output.csv")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = b"ip,score\n8.8.8.8,5\n"
        client.session.get = MagicMock(return_value=resp)
        result = client.download_result("https://example.com/download", save_path)
        assert result["success"] is True
        assert result["saved_to"] == save_path
        assert Path(save_path).read_bytes() == b"ip,score\n8.8.8.8,5\n"

    def test_download_result_creates_parent_dirs(self, client, tmp_path):
        save_path = str(tmp_path / "sub" / "dir" / "out.csv")
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = b"data"
        client.session.get = MagicMock(return_value=resp)
        client.download_result("https://example.com/dl", save_path)
        assert Path(save_path).exists()

    def test_download_result_propagates_http_error(self, client, tmp_path):
        import requests as _r
        resp = MagicMock()
        resp.raise_for_status.side_effect = _r.HTTPError("403")
        client.session.get = MagicMock(return_value=resp)
        with pytest.raises(_r.HTTPError):
            client.download_result("https://example.com/dl", str(tmp_path / "x.csv"))

    def test_malware_scan_expands_user_path(self, client, monkeypatch, tmp_path):
        sample = tmp_path / "sample.txt"
        sample.write_bytes(b"contents")
        # Make ~ resolve into our tmp_path so '~/sample.txt' is real.
        monkeypatch.setenv("HOME", str(tmp_path))
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        result = client.malware_file_scan("~/sample.txt")
        assert result["success"] is True

    def test_csv_upload_sends_correct_mime(self, client, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("a,b\n1,2\n")
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client.bulk_csv_upload(str(csv_file))
        files = client.session.request.call_args.kwargs["files"]
        # files["file"] is a (filename, fileobj, content_type) tuple
        assert files["file"][2] == "text/csv"


# ---------------------------------------------------------------------------
# Additional URL / request edge cases
# ---------------------------------------------------------------------------

class TestRequestEdgeCases:
    def test_filters_only_none_and_empty_string(self, client):
        """0 and False must NOT be filtered out — they are legal values."""
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("GET", "/test", params={"a": 0, "b": False, "c": "ok", "d": None, "e": ""})
        params = client.session.request.call_args.kwargs["params"]
        assert params == {"a": 0, "b": False, "c": "ok"}

    def test_no_params_passes_empty_dict(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("GET", "/test")
        # The implementation always normalises None → {} after filtering.
        assert client.session.request.call_args.kwargs["params"] == {}

    def test_post_without_body_sends_none(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("POST", "/test")
        assert client.session.request.call_args.kwargs["json"] is None

    def test_method_is_uppercased(self, client):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        client._request("get", "/test")
        assert client.session.request.call_args.kwargs["method"] == "GET"

    def test_save_to_expands_user(self, client, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.headers = {"content-type": "application/octet-stream"}
        resp.text = ""
        resp.content = b"x"
        client.session.request = MagicMock(return_value=resp)
        result = client._request("GET", "/test", save_to="~/out.bin")
        assert Path(result["saved_to"]).read_bytes() == b"x"

    def test_text_response_parsed_as_json_when_starts_with_brace(self, client):
        """Some IPQS endpoints return JSON without a JSON content-type header."""
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.headers = {"content-type": "text/plain"}
        resp.text = '{"success": true, "x": 1}'
        resp.content = resp.text.encode()
        resp.json.return_value = {"success": True, "x": 1}
        client.session.request = MagicMock(return_value=resp)
        result = client._request("GET", "/test")
        assert result == {"success": True, "x": 1}

    def test_text_response_parsed_as_json_when_starts_with_bracket(self, client):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.headers = {"content-type": "text/plain"}
        resp.text = "[1, 2, 3]"
        resp.content = resp.text.encode()
        resp.json.return_value = [1, 2, 3]
        client.session.request = MagicMock(return_value=resp)
        result = client._request("GET", "/test")
        assert result == [1, 2, 3]


class TestApiKeyEmbedding:
    """Every authenticated lookup must include the api_key in its path."""

    def _url_for(self, client, fn, *args, **kwargs):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        fn(*args, **kwargs)
        return client.session.request.call_args.kwargs["url"]

    @pytest.mark.parametrize("method_name,args", [
        ("ip_lookup", ("1.1.1.1",)),
        ("email_lookup", ("a@b.com",)),
        ("phone_lookup", ("+15555550123",)),
        ("url_lookup", ("https://x.com",)),
        ("device_lookup", ("fp",)),
        ("postback", ()),
        ("request_list", ()),
        ("fraud_report", ()),
        ("credit_usage", ()),
        ("login_history", ()),
        ("proxy_averages", ()),
        ("device_averages", ("tracker",)),
        ("bulk_csv_status", ("id",)),
        ("bulk_csv_list", ()),
        ("allowlist_list", ()),
        ("blocklist_list", ()),
    ])
    def test_api_key_in_url(self, client, method_name, args):
        url = self._url_for(client, getattr(client, method_name), *args)
        assert "testkey123" in url, f"{method_name} URL missing api_key: {url}"


class TestUrlEncoding:
    def _url_for(self, client, fn, *args):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        fn(*args)
        return client.session.request.call_args.kwargs["url"]

    def test_email_with_spaces(self, client):
        url = self._url_for(client, client.email_lookup, "first last@example.com")
        # quote_plus turns space into '+'
        assert "first+last%40example.com" in url

    def test_url_with_query_string(self, client):
        url = self._url_for(client, client.url_lookup, "https://x.com/?a=1&b=2")
        # '?' and '&' must be encoded so they don't terminate the path
        assert "%3F" in url
        assert "%26" in url


class TestRaiseForApiErrorsEdgeCases:
    def test_success_true_with_data_does_not_raise(self):
        IPQSClient._raise_for_api_errors({"success": True, "fraud_score": 0, "errors": []})

    def test_empty_errors_list_does_not_raise(self):
        # An empty list is falsy → not treated as an error condition.
        IPQSClient._raise_for_api_errors({"success": True, "errors": []})

    def test_missing_success_key_does_not_raise(self):
        # Some endpoints (country list) don't return a 'success' key at all.
        IPQSClient._raise_for_api_errors({"countries": ["US"]})

    def test_errors_with_dict_value(self):
        with pytest.raises(IPQSError):
            IPQSClient._raise_for_api_errors({"errors": {"field": "bad"}})


# ---------------------------------------------------------------------------
# Allowlist / blocklist parameter forwarding
# ---------------------------------------------------------------------------

class TestListMutations:
    @pytest.mark.parametrize("method_name", [
        "allowlist_create", "allowlist_delete", "blocklist_create", "blocklist_delete",
    ])
    def test_params_forwarded(self, client, method_name):
        resp = _mock_json_response({"success": True})
        client.session.request = MagicMock(return_value=resp)
        getattr(client, method_name)(
            value="1.2.3.4", value_type="ip", type="proxy", notes="test"
        )
        params = client.session.request.call_args.kwargs["params"]
        assert params == {
            "value": "1.2.3.4",
            "value_type": "ip",
            "type": "proxy",
            "notes": "test",
        }
        assert client.session.request.call_args.kwargs["method"] == "POST"
