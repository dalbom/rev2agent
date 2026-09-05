"""Structural workflow contracts; these tests do not evaluate model behavior."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = "prompts/agent_workflow.md"
SECTIONS = (
    "Request Routing",
    "Authorization and Questions",
    "Task Continuity",
    "Delegation and Review",
    "Skills and Host Capabilities",
    "Verification and Reporting",
)


def section(text, heading):
    match = re.search(rf"^## {re.escape(heading)}\s*$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing shared contract section: {heading}")
    return re.split(r"^## ", text[match.end():], maxsplit=1, flags=re.MULTILINE)[0].strip()


class TestSharedAgentWorkflow(unittest.TestCase):
    def workflow(self):
        path = ROOT / WORKFLOW
        self.assertTrue(path.is_file(), f"missing shared workflow: {WORKFLOW}")
        return path.read_text(encoding="utf-8")

    def test_both_hosts_load_shared_workflow_before_research_startup(self):
        for filename in ("AGENTS.md", "CLAUDE.md"):
            with self.subTest(host=filename):
                text = (ROOT / filename).read_text(encoding="utf-8")
                routing = section(text, "Request Routing")
                self.assertIn(WORKFLOW, routing)
                self.assertLess(text.index("## Request Routing"), text.index("## Startup Protocol"))

    def test_host_routing_contract_is_shared(self):
        contracts = [
            section((ROOT / name).read_text(encoding="utf-8"), "Request Routing")
            for name in ("AGENTS.md", "CLAUDE.md")
        ]
        self.assertEqual(contracts[0], contracts[1], "host mechanics must not change request routing")

    def test_consequential_research_contracts_have_host_parity(self):
        entrypoints = [
            (ROOT / name).read_text(encoding="utf-8")
            for name in ("AGENTS.md", "CLAUDE.md")
        ]
        for heading in (
            "Startup Protocol", "Phase Overview", "Phase Routing", "State Management",
            "Global Rules", '"Major Revision" Trigger',
        ):
            with self.subTest(contract=heading):
                self.assertEqual(section(entrypoints[0], heading), section(entrypoints[1], heading))

    def test_missing_selected_project_does_not_fall_through_to_interview(self):
        for filename in ("AGENTS.md", "CLAUDE.md"):
            with self.subTest(host=filename):
                routing = section((ROOT / filename).read_text(encoding="utf-8"), "Phase Routing")
                code = routing.split("```", 2)[1]
                self.assertIn("if user picks existing project", code)
                self.assertIn("elif no projects found", code)
                self.assertLess(code.index("if user picks existing project"), code.index("elif no projects found"))
                missing = code.split("elif no projects found:", 1)[1].split("else:", 1)[0]
                self.assertNotIn("start Phase 1", missing)

    def test_shared_contract_has_explicit_owners_for_each_behavior(self):
        workflow = self.workflow()
        for heading in SECTIONS:
            with self.subTest(contract=heading):
                self.assertTrue(section(workflow, heading))
        self.assertIn("prompts/conventions.md", workflow)
        self.assertIn("prompts/05_experiment_execution.md", workflow)

    def test_shared_workflow_does_not_embed_host_commands_or_model_names(self):
        workflow = self.workflow()
        self.assertNotRegex(workflow, r"(?im)^\s*(?:codex exec|claude (?:-p|--print))\b")
        self.assertNotRegex(workflow, r"(?i)\b(?:gpt-6-astra|claude-fable|fable 5\.1)\b")

    def test_reviewer_fallback_keeps_independence_and_state_ownership_visible(self):
        review = section(self.workflow(), "Delegation and Review").lower()
        # Keyword-level guards protect the fail-closed contract without fixing its prose.
        for concept in (r"independen", r"self.review", r"(?:cannot|must not|never|does not|do not)",
                        r"(?:main|parent).{0,40}(?:agent|state)|state.{0,40}(?:main|parent)"):
            with self.subTest(concept=concept):
                self.assertRegex(review, concept)


class TestBehaviorScenarioFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_path = ROOT / "tests/fixtures/workflow/scenarios.json"

    def fixtures(self):
        self.assertTrue(self.fixture_path.is_file(), "missing reusable behavior scenarios")
        return json.loads(self.fixture_path.read_text(encoding="utf-8"))

    def test_scenarios_have_unique_ids_and_reviewable_expectations(self):
        fixture = self.fixtures()
        self.assertEqual(fixture["schema_version"], 1)
        scenarios = fixture["scenarios"]
        ids = [scenario["id"] for scenario in scenarios]
        self.assertEqual(len(ids), len(set(ids)))
        for scenario in scenarios:
            with self.subTest(scenario=scenario["id"]):
                self.assertTrue(scenario["input"].strip())
                self.assertTrue(scenario["expected"])
                self.assertTrue(scenario["must_observe"])
                self.assertTrue(scenario["must_not_observe"])
                for relative_path in scenario["instruction_files"]:
                    self.assertTrue((ROOT / relative_path).is_file(), relative_path)
                self.assertNotIn("/home/", scenario["input"])

    def test_scenarios_cover_contract_edges_and_unknown_host_capabilities(self):
        coverage = {tag for scenario in self.fixtures()["scenarios"] for tag in scenario["tags"]}
        self.assertTrue({
            "maintenance", "prior_approval", "missing_decision", "steering",
            "delegation", "unavailable_reviewer", "archived", "session_lock",
            "experiment_verification", "external_code_privacy", "resume_identity",
            "setup_only", "explicit_launch", "missing_skill", "missing_custom_agent",
            "round_numbering", "state_grounding",
        }.issubset(coverage), f"incomplete contract coverage: {sorted(coverage)}")


if __name__ == "__main__":
    unittest.main()
