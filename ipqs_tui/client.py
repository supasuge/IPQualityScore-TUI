from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv


class IPQSError(RuntimeError):
    """Raised when IPQS returns an error or the client is misconfigured."""


class IPQSClient:
    BASE_URL = "https://www.ipqualityscore.com/api"

    def __init__(self, api_key: str | None = None, timeout: float = 30.0) -> None:
        load_dotenv()
        self.api_key = api_key or os.getenv("IPQS_API_KEY")
        if not self.api_key:
            raise IPQSError(
                "Missing IPQS_API_KEY. Export it in your environment or place it in a .env file."
            )
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "ipqs-textual-tui/0.1 (+https://www.ipqualityscore.com/documentation)",
                "Accept": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        save_to: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any:
        url = f"{self.BASE_URL}/{path.lstrip('/')}"
        headers = {}
        if extra_headers:
            headers.update(extra_headers)

        response = self.session.request(
            method=method.upper(),
            url=url,
            params={k: v for k, v in (params or {}).items() if v not in (None, "")},
            json=json_body,
            files=files,
            headers=headers or None,
            timeout=self.timeout,
        )
        response.raise_for_status()

        if save_to:
            out_path = Path(save_to).expanduser().resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(response.content)
            return {
                "success": True,
                "saved_to": str(out_path),
                "size_bytes": out_path.stat().st_size,
            }

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type or response.text.strip().startswith(("{", "[")):
            data = response.json()
            self._raise_for_api_errors(data)
            return data

        return {"success": True, "text": response.text}

    @staticmethod
    def _raise_for_api_errors(data: Any) -> None:
        if isinstance(data, dict):
            if data.get("success") is False:
                raise IPQSError(json.dumps(data, indent=2, sort_keys=True))
            errors = data.get("errors")
            if errors:
                raise IPQSError(json.dumps({"errors": errors, **data}, indent=2, sort_keys=True))

    # Core lookup APIs
    def ip_lookup(self, ip: str, **params: Any) -> Any:
        return self._request("GET", f"json/ip/{self.api_key}/{ip}", params=params)

    def email_lookup(self, email: str, **params: Any) -> Any:
        return self._request("GET", f"json/email/{self.api_key}/{quote_plus(email)}", params=params)

    def phone_lookup(self, phone: str, **params: Any) -> Any:
        return self._request("GET", f"json/phone/{self.api_key}/{quote_plus(phone)}", params=params)

    def url_lookup(self, url: str, **params: Any) -> Any:
        return self._request("GET", f"json/url/{self.api_key}/{quote_plus(url)}", params=params)

    def device_lookup(self, fingerprint: str, **params: Any) -> Any:
        return self._request("GET", f"json/device/{self.api_key}/{fingerprint}", params=params)

    def leaked_lookup(self, leak_type: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", f"json/leaked/{leak_type}/{self.api_key}", json_body=payload)

    def malware_file_scan(self, file_path: str, **params: Any) -> Any:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise IPQSError(f"File not found: {path}")
        with path.open("rb") as handle:
            return self._request(
                "POST",
                f"json/malware/{self.api_key}",
                params=params,
                files={"file": (path.name, handle)},
            )

    # Historical / account / reporting APIs
    def postback(self, **params: Any) -> Any:
        return self._request("GET", f"json/postback/{self.api_key}", params=params)

    def request_list(self, **params: Any) -> Any:
        return self._request("GET", f"json/requests/{self.api_key}/list", params=params)

    def fraud_report(self, **params: Any) -> Any:
        return self._request("GET", f"json/report/{self.api_key}", params=params)

    def credit_usage(self) -> Any:
        return self._request("GET", f"json/account/{self.api_key}")

    def login_history(self) -> Any:
        return self._request("GET", f"json/loginhistory/{self.api_key}/")

    def country_list(self) -> Any:
        return self._request("GET", "json/country/list")

    # Stats / averages
    def proxy_averages(self, **params: Any) -> Any:
        return self._request("GET", f"json/{self.api_key}/average", params=params)

    def device_averages(self, tracker_id: str, **params: Any) -> Any:
        return self._request("GET", f"json/{self.api_key}/{tracker_id}/tracker/average", params=params)

    # Bulk CSV
    def bulk_csv_upload(self, file_path: str, **params: Any) -> Any:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise IPQSError(f"CSV file not found: {path}")
        with path.open("rb") as handle:
            return self._request(
                "POST",
                f"json/csv/{self.api_key}/upload",
                params=params,
                files={"file": (path.name, handle, "text/csv")},
            )

    def bulk_csv_status(self, csv_id: str) -> Any:
        return self._request("GET", f"json/csv/{self.api_key}/status/{csv_id}")

    def bulk_csv_list(self, **params: Any) -> Any:
        return self._request("GET", f"json/csv/{self.api_key}/list", params=params)

    def download_result(self, url: str, save_to: str) -> Any:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        out_path = Path(save_to).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(response.content)
        return {
            "success": True,
            "saved_to": str(out_path),
            "size_bytes": out_path.stat().st_size,
        }

    # Allowlist / blocklist
    def allowlist_create(self, **params: Any) -> Any:
        return self._request("POST", f"json/allowlist/add/{self.api_key}", params=params)

    def allowlist_list(self) -> Any:
        return self._request("GET", f"json/allowlist/list/{self.api_key}")

    def allowlist_delete(self, **params: Any) -> Any:
        return self._request("POST", f"json/allowlist/delete/{self.api_key}", params=params)

    def blocklist_create(self, **params: Any) -> Any:
        return self._request("POST", f"json/blocklist/add/{self.api_key}", params=params)

    def blocklist_list(self) -> Any:
        return self._request("GET", f"json/blocklist/list/{self.api_key}")

    def blocklist_delete(self, **params: Any) -> Any:
        return self._request("POST", f"json/blocklist/delete/{self.api_key}", params=params)
