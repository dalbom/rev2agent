from __future__ import annotations

import importlib
import itertools
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SdkStatus:
    available: bool
    version: str | None = None
    message: str = ""


@dataclass(frozen=True)
class ThreadData:
    thread_id: str


@dataclass(frozen=True)
class StreamEventData:
    event_type: str
    summary: str
    thread_id: str
    turn_id: str
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class TurnResultData:
    turn_id: str
    status: str
    final_response: str | None
    items: list[Any] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


def get_sdk_status(
    import_module: Callable[[str], Any] = importlib.import_module,
) -> SdkStatus:
    try:
        sdk = import_module("openai_codex")
    except ModuleNotFoundError:
        return SdkStatus(
            available=False,
            message="openai_codex is not installed in this backend environment.",
        )
    return SdkStatus(
        available=True,
        version=getattr(sdk, "__version__", "unknown"),
        message="openai_codex is installed.",
    )


class FakeCodexAdapter:
    def __init__(self) -> None:
        self._thread_counter = itertools.count(1)
        self._turn_counter = itertools.count(1)
        self._threads: set[str] = set()
        self._interrupted: set[tuple[str, str]] = set()

    async def start_thread(self, *, project_dir: str, phase: int, sandbox: str) -> ThreadData:
        thread_id = f"fake-thread-{next(self._thread_counter)}"
        self._threads.add(thread_id)
        return ThreadData(thread_id=thread_id)

    async def resume_thread(self, thread_id: str, *, sandbox: str) -> ThreadData:
        self._threads.add(thread_id)
        return ThreadData(thread_id=thread_id)

    async def run_turn(self, thread_id: str, prompt: str, *, sandbox: str) -> TurnResultData:
        self._threads.add(thread_id)
        turn_id = f"fake-turn-{next(self._turn_counter)}"
        return TurnResultData(
            turn_id=turn_id,
            status="completed",
            final_response=f"Fake Codex response for: {prompt}",
            items=[{"type": "message", "text": prompt}],
            usage={"input_tokens": max(1, len(prompt.split())), "output_tokens": 6},
        )

    async def stream_turn(
        self,
        thread_id: str,
        prompt: str,
        *,
        sandbox: str,
    ) -> AsyncIterator[StreamEventData]:
        self._threads.add(thread_id)
        turn_id = f"fake-turn-{next(self._turn_counter)}"
        yield StreamEventData(
            event_type="turn_started",
            summary="Turn started",
            thread_id=thread_id,
            turn_id=turn_id,
            raw_payload={"prompt": prompt, "sandbox": sandbox},
        )
        yield StreamEventData(
            event_type="assistant_message",
            summary="Fake adapter emitted a progress message",
            thread_id=thread_id,
            turn_id=turn_id,
            raw_payload={"message": "progress"},
        )
        yield StreamEventData(
            event_type="turn_completed",
            summary="Turn completed",
            thread_id=thread_id,
            turn_id=turn_id,
            raw_payload={"status": "completed"},
        )

    async def interrupt(self, thread_id: str, turn_id: str) -> bool:
        self._interrupted.add((thread_id, turn_id))
        return True


class CodexSdkAdapter:
    def __init__(self) -> None:
        self._active_turns: dict[tuple[str, str], Any] = {}
        self._thread_clients: dict[str, Any] = {}
        self._thread_handles: dict[str, Any] = {}

    async def start_thread(self, *, project_dir: str, phase: int, sandbox: str) -> ThreadData:
        AsyncCodex, Sandbox = load_sdk_classes()
        codex = AsyncCodex()
        try:
            await codex.__aenter__()
            thread = await codex.thread_start(
                cwd=project_dir,
                sandbox=to_sdk_sandbox(Sandbox, sandbox),
            )
        except Exception:
            await codex.close()
            raise
        self._thread_clients[thread.id] = codex
        self._thread_handles[thread.id] = thread
        return ThreadData(thread_id=thread.id)

    async def resume_thread(self, thread_id: str, *, sandbox: str) -> ThreadData:
        AsyncCodex, Sandbox = load_sdk_classes()
        codex = AsyncCodex()
        try:
            await codex.__aenter__()
            thread = await codex.thread_resume(
                thread_id,
                sandbox=to_sdk_sandbox(Sandbox, sandbox),
            )
        except Exception:
            await codex.close()
            raise
        self._thread_clients[thread.id] = codex
        self._thread_handles[thread.id] = thread
        return ThreadData(thread_id=thread.id)

    async def run_turn(self, thread_id: str, prompt: str, *, sandbox: str) -> TurnResultData:
        AsyncCodex, Sandbox = load_sdk_classes()
        thread = self._thread_handles.get(thread_id)
        if thread is not None:
            try:
                result = await thread.run(prompt, sandbox=to_sdk_sandbox(Sandbox, sandbox))
                return turn_result_from_sdk(result)
            finally:
                await self._close_thread(thread_id)

        async with AsyncCodex() as codex:
            resumed = await codex.thread_resume(thread_id, sandbox=to_sdk_sandbox(Sandbox, sandbox))
            result = await resumed.run(prompt, sandbox=to_sdk_sandbox(Sandbox, sandbox))
            return turn_result_from_sdk(result)

    async def stream_turn(
        self,
        thread_id: str,
        prompt: str,
        *,
        sandbox: str,
    ) -> AsyncIterator[StreamEventData]:
        AsyncCodex, Sandbox = load_sdk_classes()
        thread = self._thread_handles.get(thread_id)
        if thread is None:
            codex = AsyncCodex()
            try:
                await codex.__aenter__()
                thread = await codex.thread_resume(
                    thread_id,
                    sandbox=to_sdk_sandbox(Sandbox, sandbox),
                )
            except Exception:
                await codex.close()
                raise
            self._thread_clients[thread.id] = codex
            self._thread_handles[thread.id] = thread
        try:
            handle = await thread.turn(prompt, sandbox=to_sdk_sandbox(Sandbox, sandbox))
            turn_id = getattr(handle, "id", None) or "unknown"
            self._active_turns[(thread_id, turn_id)] = handle
            try:
                async for notification in handle.stream():
                    event_type = notification_event_type(notification)
                    if notification_is_delta(notification) and "delta" not in event_type.lower():
                        event_type = f"{event_type}/delta"
                    yield StreamEventData(
                        event_type=event_type,
                        summary=summarize_notification(notification),
                        thread_id=thread_id,
                        turn_id=turn_id,
                        raw_payload=safe_model_dump(notification),
                    )
            finally:
                self._active_turns.pop((thread_id, turn_id), None)
        finally:
            await self._close_thread(thread_id)

    async def _close_thread(self, thread_id: str) -> None:
        codex = self._thread_clients.pop(thread_id, None)
        self._thread_handles.pop(thread_id, None)
        if codex is not None:
            await codex.close()

    async def interrupt(self, thread_id: str, turn_id: str) -> bool:
        handle = self._active_turns.get((thread_id, turn_id))
        if handle is None:
            return False
        await handle.interrupt()
        return True


def load_sdk_classes() -> tuple[Any, Any]:
    sdk = importlib.import_module("openai_codex")
    return sdk.AsyncCodex, sdk.Sandbox


def to_sdk_sandbox(Sandbox: Any, sandbox: str) -> Any:
    mapping = {
        "read_only": Sandbox.read_only,
        "workspace_write": Sandbox.workspace_write,
        "full_access": Sandbox.full_access,
    }
    return mapping[sandbox]


def turn_result_from_sdk(result: Any) -> TurnResultData:
    return TurnResultData(
        turn_id=str(getattr(result, "id", "")),
        status=str(getattr(result, "status", "")),
        final_response=getattr(result, "final_response", None),
        items=list(getattr(result, "items", []) or []),
        usage=safe_model_dump(getattr(result, "usage", None)) or {},
        error=str(getattr(result, "error", "")) if getattr(result, "error", None) else None,
    )


def _extract_summary(notification: Any) -> tuple[str, str | None]:
    root = getattr(notification, "root", None)
    payload = getattr(root, "payload", None) or getattr(notification, "payload", None)
    for source in (
        notification,
        root,
        payload,
        getattr(payload, "turn", None),
        getattr(getattr(payload, "item", None), "root", None),
    ):
        for attr in ("message", "text", "summary", "delta", "status"):
            value = getattr(source, attr, None)
            if attr == "delta" and isinstance(value, str) and value:
                # Deltas are stored unstripped so the frontend can concatenate
                # them without inventing whitespace.
                return value, "delta"
            if isinstance(value, str) and value.strip():
                return value.strip(), attr
            if value is not None and attr == "status":
                return str(value), attr
    return "", None


def summarize_notification(notification: Any) -> str:
    summary, source_attr = _extract_summary(notification)
    if source_attr is not None:
        return summary
    method = notification_event_type(notification)
    if isinstance(method, str) and method.strip():
        return method.strip()
    return type(notification).__name__


def notification_is_delta(notification: Any) -> bool:
    return _extract_summary(notification)[1] == "delta"


def notification_event_type(notification: Any) -> str:
    root = getattr(notification, "root", None)
    for source in (root, notification):
        method = getattr(source, "method", None)
        if isinstance(method, str) and method.strip():
            return method.strip()
    return type(notification).__name__


def safe_model_dump(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {"value": dumped}
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    if isinstance(value, dict):
        return value
    return {"value": str(value)}
