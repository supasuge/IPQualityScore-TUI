from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FieldDef:
    name: str
    label: str
    required: bool = False
    placeholder: str = ""
    default: str = ""
    secret: bool = False


@dataclass(slots=True)
class Operation:
    key: str
    category: str
    label: str
    method_name: str
    description: str
    fields: list[FieldDef] = field(default_factory=list)
    static_kwargs: dict[str, Any] = field(default_factory=dict)


OPERATIONS: list[Operation] = [
    Operation(
        key="ip_lookup",
        category="Realtime Lookups",
        label="IP / Proxy Lookup",
        method_name="ip_lookup",
        description="Proxy & VPN Detection API with optional transaction, user agent, and strictness parameters.",
        fields=[
            FieldDef("ip", "IP address", True, "8.8.8.8"),
            FieldDef("strictness", "Strictness", False, "0-3", "1"),
            FieldDef("allow_public_access_points", "Allow public access points", False, "true/false"),
            FieldDef("lighter_penalties", "Lighter penalties", False, "true/false"),
            FieldDef("fast", "Fast mode", False, "true/false"),
            FieldDef("mobile", "Force mobile", False, "true/false"),
            FieldDef("user_agent", "User-Agent", False),
            FieldDef("user_language", "User language", False, "en-US"),
            FieldDef("transaction_strictness", "Transaction strictness", False, "0-2"),
            FieldDef("billing_email", "Billing email", False),
            FieldDef("billing_phone", "Billing phone", False),
            FieldDef("billing_country", "Billing country", False, "US"),
            FieldDef("billing_address_1", "Billing address 1", False),
            FieldDef("billing_city", "Billing city", False),
            FieldDef("billing_region", "Billing region", False),
            FieldDef("billing_postcode", "Billing postcode", False),
        ],
    ),
    Operation(
        key="email_lookup",
        category="Realtime Lookups",
        label="Email Verification",
        method_name="email_lookup",
        description="Email Verification API for validity, deliverability, disposable domains, and fraud signals.",
        fields=[
            FieldDef("email", "Email address", True, "user@example.com"),
            FieldDef("timeout", "SMTP timeout", False, "seconds"),
            FieldDef("fast", "Fast mode", False, "true/false"),
            FieldDef("abuse_strictness", "Abuse strictness", False, "0-2"),
            FieldDef("suggest_domain", "Suggest domain", False, "true/false"),
        ],
    ),
    Operation(
        key="phone_lookup",
        category="Realtime Lookups",
        label="Phone Validation",
        method_name="phone_lookup",
        description="Phone number validation and fraud risk checks.",
        fields=[
            FieldDef("phone", "Phone number", True, "+15555550123"),
            FieldDef("country", "Country", False, "US"),
            FieldDef("strictness", "Strictness", False, "0-2", "1"),
            FieldDef("fast", "Fast mode", False, "true/false"),
        ],
    ),
    Operation(
        key="url_lookup",
        category="Realtime Lookups",
        label="Malicious URL / Domain Lookup",
        method_name="url_lookup",
        description="Malicious URL Scanner API and domain reputation checks.",
        fields=[
            FieldDef("url", "URL or domain", True, "https://example.com/login"),
            FieldDef("strictness", "Strictness", False, "0-2", "1"),
            FieldDef("fast", "Fast mode", False, "true/false"),
            FieldDef("timeout", "Page fetch timeout", False, "seconds"),
        ],
    ),
    Operation(
        key="device_lookup",
        category="Realtime Lookups",
        label="Device Fingerprint Lookup",
        method_name="device_lookup",
        description="Device Fingerprint API lookup by fingerprint / device identifier.",
        fields=[
            FieldDef("fingerprint", "Device fingerprint", True),
            FieldDef("strictness", "Strictness", False, "0-2", "1"),
            FieldDef("allow_public_access_points", "Allow public access points", False, "true/false"),
            FieldDef("lighter_penalties", "Lighter penalties", False, "true/false"),
        ],
    ),
    Operation(
        key="leak_password",
        category="Realtime Lookups",
        label="Dark Web Leak Lookup: Password",
        method_name="leaked_lookup",
        description="Dark Web Leak API password lookup.",
        fields=[FieldDef("password", "Password", True, secret=True)],
        static_kwargs={"leak_type": "password"},
    ),
    Operation(
        key="leak_emailpass",
        category="Realtime Lookups",
        label="Dark Web Leak Lookup: Email + Password",
        method_name="leaked_lookup",
        description="Dark Web Leak API combined email + password lookup.",
        fields=[
            FieldDef("email", "Email address", True),
            FieldDef("password", "Password", True, secret=True),
        ],
        static_kwargs={"leak_type": "emailpass"},
    ),
    Operation(
        key="malware_scan",
        category="Realtime Lookups",
        label="Malware File Scan",
        method_name="malware_file_scan",
        description="Upload a file to the Malware File Scanner API.",
        fields=[FieldDef("file_path", "File path", True, "~/sample.exe")],
    ),
    Operation(
        key="postback",
        category="History / Reporting",
        label="Postback / Retrieve Request",
        method_name="postback",
        description="Use the Postback API to retrieve or update prior requests using request_id or custom tracking fields.",
        fields=[
            FieldDef("request_id", "Request ID", False),
            FieldDef("type", "Original request type", False, "proxy|email|devicetracker|mobiletracker"),
            FieldDef("UserID", "Custom UserID", False),
            FieldDef("transactionID", "Custom transactionID", False),
            FieldDef("update[ConversionStatus]", "Update ConversionStatus", False, "true/false"),
            FieldDef("update[ConversionDate]", "Update ConversionDate", False, "YYYY-MM-DD"),
            FieldDef("update[ClickDate]", "Update ClickDate", False, "YYYY-MM-DD"),
        ],
    ),
    Operation(
        key="request_list",
        category="History / Reporting",
        label="Request List",
        method_name="request_list",
        description="Retrieve historical requests across supported lookup types.",
        fields=[
            FieldDef("type", "Request type", True, "proxy|email|devicetracker|mobiletracker"),
            FieldDef("start_date", "Start date", False, "YYYY-MM-DD"),
            FieldDef("ip_address", "IP filter", False),
            FieldDef("device_id", "Device filter", False),
            FieldDef("page", "Page", False, "1"),
        ],
    ),
    Operation(
        key="fraud_report",
        category="History / Reporting",
        label="Fraud Reporting",
        method_name="fraud_report",
        description="Report fraudulent events back to IPQS to improve scoring.",
        fields=[
            FieldDef("type", "Type", True, "proxy|email|phone|url|device"),
            FieldDef("ip", "IP", False),
            FieldDef("email", "Email", False),
            FieldDef("phone", "Phone", False),
            FieldDef("url", "URL", False),
            FieldDef("device_id", "Device ID", False),
            FieldDef("reason", "Reason", False),
        ],
    ),
    Operation(
        key="proxy_averages",
        category="History / Reporting",
        label="Proxy Stats & Averages",
        method_name="proxy_averages",
        description="Proxy & VPN Detection Stats & Averages API.",
        fields=[
            FieldDef("days", "Days", False, "7"),
            FieldDef("strictness", "Strictness", False, "0-2"),
            FieldDef("userID", "Custom tracking userID", False),
            FieldDef("transactionID", "Custom tracking transactionID", False),
        ],
    ),
    Operation(
        key="device_averages",
        category="History / Reporting",
        label="Device Tracker Stats & Averages",
        method_name="device_averages",
        description="Device Fingerprint stats by tracker ID.",
        fields=[
            FieldDef("tracker_id", "Tracker ID", True),
            FieldDef("days", "Days", False, "7"),
            FieldDef("userID", "Custom tracking userID", False),
            FieldDef("transactionID", "Custom tracking transactionID", False),
        ],
    ),
    Operation(
        key="credit_usage",
        category="Account / Meta",
        label="Credit Usage",
        method_name="credit_usage",
        description="Current credits and account usage for the billing period.",
    ),
    Operation(
        key="login_history",
        category="Account / Meta",
        label="Login History",
        method_name="login_history",
        description="Fetch account login history.",
    ),
    Operation(
        key="country_list",
        category="Account / Meta",
        label="Country List",
        method_name="country_list",
        description="Fetch the IPQS country list metadata.",
    ),
    Operation(
        key="csv_upload",
        category="Bulk CSV",
        label="Bulk CSV Upload",
        method_name="bulk_csv_upload",
        description="Upload a CSV for bulk IP, email, phone, or URL validation.",
        fields=[
            FieldDef("file_path", "CSV path", True, "~/input.csv"),
            FieldDef("type", "Lookup type", False, "proxy|email|phone|url"),
            FieldDef("name", "Job name", False),
        ],
    ),
    Operation(
        key="csv_status",
        category="Bulk CSV",
        label="Bulk CSV Status",
        method_name="bulk_csv_status",
        description="Check bulk CSV processing status and download options.",
        fields=[FieldDef("csv_id", "CSV ID", True)],
    ),
    Operation(
        key="csv_list",
        category="Bulk CSV",
        label="Bulk CSV List",
        method_name="bulk_csv_list",
        description="List previously uploaded CSV jobs.",
        fields=[FieldDef("page", "Page", False, "1")],
    ),
    Operation(
        key="download_result",
        category="Bulk CSV",
        label="Download Result URL",
        method_name="download_result",
        description="Convenience helper: save a downloadable IPQS result URL to disk.",
        fields=[
            FieldDef("url", "Download URL", True),
            FieldDef("save_to", "Save path", True, "~/Downloads/ipqs-results.csv"),
        ],
    ),
    Operation(
        key="allowlist_create",
        category="Allowlist / Blocklist",
        label="Create Allowlist Entry",
        method_name="allowlist_create",
        description="Create an allowlist entry.",
        fields=[
            FieldDef("value", "Value", True),
            FieldDef("value_type", "Value type", True, "ip|email|phone|domain"),
            FieldDef("type", "List type", True, "proxy|email|phone|url"),
            FieldDef("notes", "Notes", False),
        ],
    ),
    Operation(
        key="allowlist_list",
        category="Allowlist / Blocklist",
        label="List Allowlist Entries",
        method_name="allowlist_list",
        description="List allowlist entries.",
    ),
    Operation(
        key="allowlist_delete",
        category="Allowlist / Blocklist",
        label="Delete Allowlist Entry",
        method_name="allowlist_delete",
        description="Delete an allowlist entry by value/value_type/type.",
        fields=[
            FieldDef("value", "Value", True),
            FieldDef("value_type", "Value type", True, "ip|email|phone|domain"),
            FieldDef("type", "List type", True, "proxy|email|phone|url"),
        ],
    ),
    Operation(
        key="blocklist_create",
        category="Allowlist / Blocklist",
        label="Create Blocklist Entry",
        method_name="blocklist_create",
        description="Create a blocklist entry.",
        fields=[
            FieldDef("value", "Value", True),
            FieldDef("value_type", "Value type", True, "ip|email|phone|domain"),
            FieldDef("type", "List type", True, "proxy|email|phone|url"),
            FieldDef("notes", "Notes", False),
        ],
    ),
    Operation(
        key="blocklist_list",
        category="Allowlist / Blocklist",
        label="List Blocklist Entries",
        method_name="blocklist_list",
        description="List blocklist entries.",
    ),
    Operation(
        key="blocklist_delete",
        category="Allowlist / Blocklist",
        label="Delete Blocklist Entry",
        method_name="blocklist_delete",
        description="Delete a blocklist entry by value/value_type/type.",
        fields=[
            FieldDef("value", "Value", True),
            FieldDef("value_type", "Value type", True, "ip|email|phone|domain"),
            FieldDef("type", "List type", True, "proxy|email|phone|url"),
        ],
    ),
]

OPERATIONS_BY_KEY = {operation.key: operation for operation in OPERATIONS}
