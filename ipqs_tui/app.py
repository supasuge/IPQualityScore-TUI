from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from rich.markup import escape
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Label, OptionList, Pretty, Static
from textual.widgets.option_list import Option

from .client import IPQSClient, IPQSError
from .operations import FieldDef, OPERATIONS, OPERATIONS_BY_KEY, Operation

_ID_REPLACE = re.compile(r"[^A-Za-z0-9_-]")


def _field_id(field_name: str) -> str:
    """Convert an IPQS field name into a Textual-safe widget id.

    Textual ids only allow [A-Za-z0-9_-] and must not start with a digit.
    Some IPQS parameters use bracket notation (e.g. 'update[ConversionStatus]')
    so we slug those characters to underscores.
    """
    slug = _ID_REPLACE.sub("_", field_name)
    if slug and slug[0].isdigit():
        slug = f"_{slug}"
    return f"field-{slug}"


class IPQSTUI(App[None]):
    CSS = """
    Screen {
        layout: vertical;
    }

    #body {
        height: 1fr;
    }

    #ops-pane {
        width: 34;
        border: round $accent;
    }

    #form-pane {
        width: 48;
        border: round $primary;
    }

    #result-pane {
        width: 1fr;
        border: round $success;
    }

    #form-scroll, #result-scroll {
        height: 1fr;
    }

    .section-title {
        text-style: bold;
        color: $text;
        padding: 0 1;
    }

    .field-label {
        margin: 1 1 0 1;
    }

    Input {
        margin: 0 1 0 1;
    }

    #buttons {
        height: auto;
        margin: 1;
    }

    Button {
        margin-right: 1;
    }

    #status {
        height: auto;
        min-height: 3;
        padding: 0 1;
    }
    """

    BINDINGS = [
        ("ctrl+r", "run_selected", "Run"),
        ("ctrl+l", "clear_fields", "Clear Fields"),
        ("ctrl+s", "save_result", "Save Result"),
        ("q", "quit", "Quit"),
    ]

    selected_key: reactive[str] = reactive(OPERATIONS[0].key)

    def __init__(self) -> None:
        super().__init__()
        self.client: IPQSClient | None = None
        self.field_inputs: dict[str, Input] = {}
        self.latest_result: Any = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="ops-pane"):
                yield Static("Operations", classes="section-title")
                yield OptionList(*self._build_operation_options(), id="operations")
            with Vertical(id="form-pane"):
                yield Static("Parameters", classes="section-title")
                yield Static(id="op-description")
                with VerticalScroll(id="form-scroll"):
                    yield Vertical(id="dynamic-form")
                with Horizontal(id="buttons"):
                    yield Button("Run", variant="success", id="run")
                    yield Button("Clear", variant="default", id="clear")
                    yield Button("Save JSON", variant="primary", id="save")
                yield Static(id="status")
            with Vertical(id="result-pane"):
                yield Static("Result", classes="section-title")
                with VerticalScroll(id="result-scroll"):
                    yield Pretty({"status": "waiting for first request"}, id="result")
        yield Footer()

    async def on_mount(self) -> None:
        try:
            self.client = IPQSClient()
            self._set_status("Loaded IPQS_API_KEY successfully.")
        except Exception as exc:
            self._set_status(str(exc), error=True)
        await self._render_selected_operation()

    def _build_operation_options(self) -> list[Option]:
        options: list[Option] = []
        current_category = None
        for op in OPERATIONS:
            if op.category != current_category:
                current_category = op.category
                options.append(
                    Option(
                        f"── {current_category} ──",
                        id=f"sep::{current_category}",
                        disabled=True,
                    )
                )
            options.append(Option(op.label, id=op.key))
        return options

    def _set_status(self, message: str, *, error: bool = False) -> None:
        # Bare bracket prefixes get parsed as Rich markup tags; use a styled
        # tag and escape the message body so user data with brackets is safe.
        tag = "[bold red]ERROR[/]" if error else "[bold green]OK[/]"
        self.query_one("#status", Static).update(f"{tag} {escape(message)}")

    def _selected_operation(self) -> Operation:
        return OPERATIONS_BY_KEY[self.selected_key]

    async def _render_selected_operation(self) -> None:
        operation = self._selected_operation()
        self.query_one("#op-description", Static).update(operation.description)
        container = self.query_one("#dynamic-form", Vertical)
        # Await the removal so new widgets don't collide with the old ids.
        await container.remove_children()
        self.field_inputs.clear()

        widgets: list[Label | Input] = []
        for field in operation.fields:
            widgets.append(Label(self._field_label_text(field), classes="field-label"))
            input_widget = Input(
                placeholder=field.placeholder,
                password=field.secret,
                value=field.default,
                id=_field_id(field.name),
            )
            self.field_inputs[field.name] = input_widget
            widgets.append(input_widget)
        if widgets:
            await container.mount_all(widgets)

    @staticmethod
    def _field_label_text(field: FieldDef) -> str:
        return f"{field.label}{' *' if field.required else ''}"

    @on(OptionList.OptionSelected, "#operations")
    async def on_operation_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id and not event.option.disabled and not event.option.id.startswith("sep::"):
            self.selected_key = event.option.id
            await self._render_selected_operation()

    @on(Button.Pressed, "#clear")
    def clear_pressed(self) -> None:
        self.action_clear_fields()

    @on(Button.Pressed, "#run")
    def run_pressed(self) -> None:
        self.action_run_selected()

    @on(Button.Pressed, "#save")
    def save_pressed(self) -> None:
        self.action_save_result()

    def action_clear_fields(self) -> None:
        for widget in self.field_inputs.values():
            widget.value = ""
        self._set_status("Cleared current form fields.")

    def action_save_result(self) -> None:
        if self.latest_result is None:
            self._set_status("No result available to save yet.", error=True)
            return

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_path = f"ipqs-result-{self.selected_key}-{ts}.json"
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(self.latest_result, handle, indent=2, sort_keys=True)
        self._set_status(f"Saved result to {out_path}")

    def action_run_selected(self) -> None:
        if not self.client:
            self._set_status("Client not initialized. Check IPQS_API_KEY.", error=True)
            return

        operation = self._selected_operation()
        try:
            kwargs = self._collect_kwargs(operation)
        except IPQSError as exc:
            self._set_status(str(exc), error=True)
            return

        self._set_status(f"Running {operation.label}…")
        self._run_in_worker(operation, kwargs)

    @work(exclusive=True, thread=True, group="api")
    def _run_in_worker(self, operation: Operation, kwargs: dict[str, str]) -> None:
        try:
            method = getattr(self.client, operation.method_name)
            result = self._invoke(method, operation, kwargs)
            self.call_from_thread(self._on_request_success, operation, result)
        except Exception as exc:
            self.call_from_thread(self._on_request_error, operation, exc)

    def _on_request_success(self, operation: Operation, result: Any) -> None:
        self.latest_result = result
        self.query_one("#result", Pretty).update(result)
        self._set_status(f"{operation.label} completed.")

    def _on_request_error(self, operation: Operation, exc: BaseException) -> None:
        error_payload = {"error": str(exc), "operation": operation.label}
        self.latest_result = error_payload
        self.query_one("#result", Pretty).update(error_payload)
        self._set_status(str(exc), error=True)

    def _collect_kwargs(self, operation: Operation) -> dict[str, str]:
        kwargs: dict[str, str] = {}
        for field in operation.fields:
            value = self.field_inputs[field.name].value.strip()
            if field.required and not value:
                raise IPQSError(f"Missing required field: {field.label}")
            if value:
                kwargs[field.name] = value
        return kwargs

    def _invoke(self, method: Any, operation: Operation, kwargs: dict[str, str]) -> Any:
        if operation.key in {"leak_password", "leak_emailpass"}:
            leak_type = operation.static_kwargs["leak_type"]
            payload = dict(kwargs)
            return method(leak_type=leak_type, payload=payload)

        if operation.key == "ip_lookup":
            ip = kwargs.pop("ip")
            return method(ip, **kwargs)

        if operation.key == "email_lookup":
            email = kwargs.pop("email")
            return method(email, **kwargs)

        if operation.key == "phone_lookup":
            phone = kwargs.pop("phone")
            return method(phone, **kwargs)

        if operation.key == "url_lookup":
            url = kwargs.pop("url")
            return method(url, **kwargs)

        if operation.key == "device_lookup":
            fingerprint = kwargs.pop("fingerprint")
            return method(fingerprint, **kwargs)

        if operation.key == "malware_scan":
            file_path = kwargs.pop("file_path")
            return method(file_path, **kwargs)

        if operation.key == "device_averages":
            tracker_id = kwargs.pop("tracker_id")
            return method(tracker_id, **kwargs)

        if operation.key == "csv_upload":
            file_path = kwargs.pop("file_path")
            return method(file_path, **kwargs)

        if operation.key == "csv_status":
            csv_id = kwargs.pop("csv_id")
            return method(csv_id)

        if operation.key == "download_result":
            url = kwargs.pop("url")
            save_to = kwargs.pop("save_to")
            return method(url, save_to)

        return method(**kwargs)


def main() -> None:
    app = IPQSTUI()
    app.run()


if __name__ == "__main__":
    main()
