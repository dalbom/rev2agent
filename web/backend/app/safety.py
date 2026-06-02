from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class SandboxName(StrEnum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    FULL_ACCESS = "full_access"


@dataclass(frozen=True)
class SafetyDecision:
    risk_level: str
    sandbox: SandboxName
    requires_approval: bool
    impact: str
    audit_details: dict[str, Any] = field(default_factory=dict)


HIGH_RISK_PATTERNS = (
    "install",
    "download dataset",
    "dataset download",
    "gpu training",
    "start gpu",
    "long experiment",
    "run experiment",
    "delete",
    "remove files",
    "full_access",
    "full access",
    "outside repository",
    "outside the repository",
    "network-heavy",
    "network heavy",
)


def classify_action(
    *,
    phase: int,
    action: str,
    requested_sandbox: SandboxName | None = None,
    command: str | None = None,
    target_paths: list[str] | None = None,
    expected_duration: str | None = None,
    network_use: str | None = None,
    can_modify_files: bool | None = None,
) -> SafetyDecision:
    normalized = action.lower()
    sandbox = requested_sandbox or default_sandbox_for_action(phase, normalized)
    is_high_risk = sandbox == SandboxName.FULL_ACCESS or any(
        pattern in normalized for pattern in HIGH_RISK_PATTERNS
    )

    audit_details = {
        "phase": phase,
        "action": action,
        "command": command,
        "target_paths": target_paths or [],
        "expected_duration": expected_duration,
        "network_use": network_use,
        "can_modify_files": can_modify_files,
    }

    if is_high_risk:
        return SafetyDecision(
            risk_level="high",
            sandbox=sandbox,
            requires_approval=True,
            impact=high_risk_impact(action, sandbox),
            audit_details=audit_details,
        )

    if sandbox == SandboxName.WORKSPACE_WRITE:
        return SafetyDecision(
            risk_level="medium",
            sandbox=sandbox,
            requires_approval=False,
            impact="This action can create or edit files inside the selected project.",
            audit_details=audit_details,
        )

    return SafetyDecision(
        risk_level="low",
        sandbox=SandboxName.READ_ONLY,
        requires_approval=False,
        impact="This action reads Rev2Agent state or project files without modifying them.",
        audit_details=audit_details,
    )


def default_sandbox_for_action(phase: int, normalized_action: str) -> SandboxName:
    if "review" in normalized_action and "write" not in normalized_action:
        return SandboxName.READ_ONLY
    if "read" in normalized_action or "inspect" in normalized_action:
        return SandboxName.READ_ONLY
    if phase == 8 and "reviewer" in normalized_action and "write" not in normalized_action:
        return SandboxName.READ_ONLY
    return SandboxName.WORKSPACE_WRITE


def high_risk_impact(action: str, sandbox: SandboxName) -> str:
    if sandbox == SandboxName.FULL_ACCESS:
        return (
            "This action requests full filesystem access. It can read or modify files "
            "outside the Rev2Agent workspace and requires separate approval."
        )
    lowered = action.lower()
    if "experiment" in lowered or "training" in lowered:
        return (
            "This starts a long-running experiment or training job. It may modify "
            "project files, produce logs/results, and consume local compute."
        )
    if "delete" in lowered or "remove" in lowered:
        return "This can delete files and cannot be started without explicit approval."
    if "download" in lowered or "network" in lowered:
        return "This may use significant network access or download data before continuing."
    if "install" in lowered:
        return "This installs packages and can change the local project environment."
    return "This high-risk action requires explicit approval before it can start."


def redact_secrets(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if looks_secret_key(key) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return redact_secret_text(value)
    return value


def looks_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(part in lowered for part in ("api_key", "token", "secret", "password"))


def redact_secret_text(text: str) -> str:
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"\b(sk-[A-Za-z0-9._\-]+|xai-[A-Za-z0-9._\-]+|AIzaSy[A-Za-z0-9._\-]+)", "[REDACTED]", text)
    return text
