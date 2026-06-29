from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from app.codex_adapter import (
    CodexSdkAdapter,
    FakeCodexAdapter,
    TurnResultData,
    _extract_summary,
    get_sdk_status,
    notification_is_delta,
    summarize_notification,
)


def test_sdk_status_reports_unavailable_without_import_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_import(name: str):
        if name == "openai_codex":
            raise ModuleNotFoundError(name)
        return importlib.import_module(name)

    status = get_sdk_status(import_module=fake_import)

    assert status.available is False
    assert "openai_codex" in status.message


def test_sdk_status_reports_installed_sdk() -> None:
    status = get_sdk_status()

    assert status.available is True
    assert status.version


@pytest.mark.asyncio
async def test_fake_adapter_starts_resumes_streams_and_interrupts() -> None:
    adapter = FakeCodexAdapter()

    started = await adapter.start_thread(project_dir="demo", phase=2, sandbox="read_only")
    resumed = await adapter.resume_thread(started.thread_id, sandbox="workspace_write")
    stream = [
        event
        async for event in adapter.stream_turn(resumed.thread_id, "Summarize phase", sandbox="read_only")
    ]
    interrupted = await adapter.interrupt(resumed.thread_id, stream[-1].turn_id)

    assert started.thread_id.startswith("fake-thread-")
    assert resumed.thread_id == started.thread_id
    assert [event.event_type for event in stream] == ["turn_started", "assistant_message", "turn_completed"]
    assert stream[-1].turn_id.startswith("fake-turn-")
    assert interrupted is True


@pytest.mark.asyncio
async def test_fake_adapter_run_turn_returns_metadata() -> None:
    adapter = FakeCodexAdapter()
    thread = await adapter.start_thread(project_dir="demo", phase=3, sandbox="workspace_write")

    result = await adapter.run_turn(thread.thread_id, "Create a research plan", sandbox="workspace_write")

    assert isinstance(result, TurnResultData)
    assert result.turn_id.startswith("fake-turn-")
    assert result.status == "completed"
    assert result.final_response
    assert result.usage["input_tokens"] > 0


def test_openai_codex_import_isolated_to_adapter_module() -> None:
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.glob("*.py"):
        if path.name == "codex_adapter.py":
            continue
        if "openai_codex" in path.read_text(encoding="utf-8"):
            offenders.append(path.name)

    assert offenders == []


def test_real_adapter_can_be_constructed_without_starting_sdk_runtime() -> None:
    adapter = CodexSdkAdapter()

    assert adapter is not None


def test_notification_summary_prefers_agent_message_text() -> None:
    class AgentMessage:
        text = "Here is the final answer."

    class ThreadItem:
        root = AgentMessage()

    class Payload:
        item = ThreadItem()

    class Root:
        method = "item/completed"
        payload = Payload()

    class Notification:
        root = Root()

    assert summarize_notification(Notification()) == "Here is the final answer."


def test_extract_summary_returns_delta_unstripped_with_delta_source() -> None:
    class Notification:
        method = "codex/event/agent_message"
        delta = " chunk with spaces "

    summary, source_attr = _extract_summary(Notification())

    assert summary == " chunk with spaces "
    assert source_attr == "delta"
    assert summarize_notification(Notification()) == " chunk with spaces "
    assert notification_is_delta(Notification()) is True


def test_extract_summary_keeps_whitespace_only_delta() -> None:
    class Notification:
        method = "codex/event/agent_message"
        delta = " "

    summary, source_attr = _extract_summary(Notification())

    assert summary == " "
    assert source_attr == "delta"
    assert notification_is_delta(Notification()) is True


def test_extract_summary_strips_non_delta_attributes() -> None:
    class Notification:
        method = "item/completed"
        message = "  Final answer.  "
        delta = " ignored because message wins "

    summary, source_attr = _extract_summary(Notification())

    assert summary == "Final answer."
    assert source_attr == "message"
    assert notification_is_delta(Notification()) is False


def test_extract_summary_returns_no_source_when_nothing_matches() -> None:
    class Notification:
        method = "turn/started"

    summary, source_attr = _extract_summary(Notification())

    assert summary == ""
    assert source_attr is None
    assert summarize_notification(Notification()) == "turn/started"
    assert notification_is_delta(Notification()) is False


@pytest.mark.asyncio
async def test_real_adapter_tags_delta_notifications_in_event_type(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSandbox:
        read_only = "read_only"
        workspace_write = "workspace_write"
        full_access = "full_access"

    class DeltaNotification:
        method = "codex/event/agent_message"
        delta = " streamed chunk "

        def model_dump(self, mode: str = "json") -> dict[str, str]:
            return {"delta": self.delta}

    class AlreadyTaggedDeltaNotification:
        method = "codex/event/agent_message_delta"
        delta = "next"

        def model_dump(self, mode: str = "json") -> dict[str, str]:
            return {"delta": self.delta}

    class MessageNotification:
        method = "item/completed"
        message = "Final answer."

        def model_dump(self, mode: str = "json") -> dict[str, str]:
            return {"message": self.message}

    class FakeHandle:
        id = "sdk-turn-1"

        async def stream(self):
            yield DeltaNotification()
            yield AlreadyTaggedDeltaNotification()
            yield MessageNotification()

    class FakeThread:
        id = "sdk-thread-1"

        async def turn(self, prompt: str, *, sandbox: str):
            return FakeHandle()

    class FakeAsyncCodex:
        def __init__(self) -> None:
            self.thread = FakeThread()

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb) -> None:
            await self.close()

        async def close(self) -> None:
            pass

        async def thread_start(self, *, cwd: str, sandbox: str):
            return self.thread

    monkeypatch.setattr(
        "app.codex_adapter.load_sdk_classes",
        lambda: (FakeAsyncCodex, FakeSandbox),
    )
    adapter = CodexSdkAdapter()

    thread = await adapter.start_thread(project_dir="demo", phase=1, sandbox="workspace_write")
    stream = [
        event
        async for event in adapter.stream_turn(thread.thread_id, "Run phase", sandbox="workspace_write")
    ]

    assert [event.event_type for event in stream] == [
        "codex/event/agent_message/delta",
        "codex/event/agent_message_delta",
        "item/completed",
    ]
    assert [event.summary for event in stream] == [
        " streamed chunk ",
        "next",
        "Final answer.",
    ]


@pytest.mark.asyncio
async def test_real_adapter_streams_turn_on_fresh_thread_without_resuming(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSandbox:
        read_only = "read_only"
        workspace_write = "workspace_write"
        full_access = "full_access"

    class FakeNotification:
        message = "streamed from fresh thread"

        def model_dump(self, mode: str = "json") -> dict[str, str]:
            return {"message": self.message, "mode": mode}

    class FakeHandle:
        id = "sdk-turn-1"

        async def stream(self):
            yield FakeNotification()

    class FakeThread:
        id = "sdk-thread-1"

        def __init__(self) -> None:
            self.turn_inputs: list[str] = []

        async def turn(self, prompt: str, *, sandbox: str):
            self.turn_inputs.append(prompt)
            return FakeHandle()

    class FakeAsyncCodex:
        instances: list["FakeAsyncCodex"] = []

        def __init__(self) -> None:
            self.thread = FakeThread()
            self.closed = False
            FakeAsyncCodex.instances.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, _exc_type, _exc, _tb) -> None:
            await self.close()

        async def close(self) -> None:
            self.closed = True

        async def thread_start(self, *, cwd: str, sandbox: str):
            return self.thread

        async def thread_resume(self, thread_id: str, *, sandbox: str):
            raise AssertionError("freshly started threads should stream through their existing thread handle")

    monkeypatch.setattr(
        "app.codex_adapter.load_sdk_classes",
        lambda: (FakeAsyncCodex, FakeSandbox),
    )
    adapter = CodexSdkAdapter()

    thread = await adapter.start_thread(project_dir="demo", phase=1, sandbox="workspace_write")
    stream = [event async for event in adapter.stream_turn(thread.thread_id, "Run phase", sandbox="workspace_write")]

    assert thread.thread_id == "sdk-thread-1"
    assert [event.summary for event in stream] == ["streamed from fresh thread"]
    assert FakeAsyncCodex.instances[0].thread.turn_inputs == ["Run phase"]
    assert FakeAsyncCodex.instances[0].closed is True
