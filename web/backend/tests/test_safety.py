from __future__ import annotations

from app.safety import (
    SandboxName,
    classify_action,
    redact_secrets,
)


def test_reading_project_state_defaults_to_read_only() -> None:
    decision = classify_action(phase=1, action="Read project state and summaries")

    assert decision.sandbox == SandboxName.READ_ONLY
    assert decision.risk_level == "low"
    assert decision.requires_approval is False


def test_literature_output_writing_uses_workspace_write() -> None:
    decision = classify_action(phase=2, action="Write literature search output")

    assert decision.sandbox == SandboxName.WORKSPACE_WRITE
    assert decision.risk_level == "medium"
    assert decision.requires_approval is False


def test_running_experiments_requires_explicit_approval() -> None:
    decision = classify_action(
        phase=5,
        action="Run experiment scripts for round 1",
        command="bash scripts/run_all.sh",
        target_paths=["demo_project/experiment"],
        expected_duration="12 hours",
        network_use="none",
        can_modify_files=True,
    )

    assert decision.sandbox == SandboxName.WORKSPACE_WRITE
    assert decision.risk_level == "high"
    assert decision.requires_approval is True
    assert "long-running experiment" in decision.impact.lower()
    assert decision.audit_details["command"] == "bash scripts/run_all.sh"


def test_full_access_requires_separate_high_risk_approval() -> None:
    decision = classify_action(
        phase=5,
        action="Use Sandbox.full_access to inspect system files",
        requested_sandbox=SandboxName.FULL_ACCESS,
    )

    assert decision.sandbox == SandboxName.FULL_ACCESS
    assert decision.risk_level == "high"
    assert decision.requires_approval is True
    assert "full filesystem access" in decision.impact.lower()


def test_known_high_risk_operations_require_approval() -> None:
    risky_actions = [
        "Install packages",
        "Download dataset",
        "Start GPU training",
        "Delete old checkpoints",
        "Run command outside repository",
        "Perform network-heavy literature fetch",
    ]

    for action in risky_actions:
        decision = classify_action(phase=5, action=action)
        assert decision.requires_approval is True, action
        assert decision.risk_level == "high", action


def test_secret_redaction_removes_browser_exposed_secrets() -> None:
    payload = {
        "api_key": "sk-secret-value",
        "nested": {"token": "xai-private-token"},
        "message": "Authorization: Bearer abc123",
        "safe": "visible",
    }

    redacted = redact_secrets(payload)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["token"] == "[REDACTED]"
    assert redacted["message"] == "Authorization: Bearer [REDACTED]"
    assert redacted["safe"] == "visible"
