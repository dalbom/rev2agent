"""Regression tests for cross-phase prompt and state invariants."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


class TestCanonicalRoundState(unittest.TestCase):
    def test_schema_persists_current_round_short_name(self):
        conventions = read("prompts/conventions.md")
        match = re.search(r"```json\n(.*?)\n```", conventions, re.DOTALL)
        self.assertIsNotNone(match, "canonical state schema JSON block is missing")
        schema = json.loads(match.group(1))
        self.assertIn("current_round_short_name", schema)
        self.assertEqual(schema["current_round_short_name"], "")

    def test_sub_step_enum_includes_phase6_review_reentry(self):
        conventions = read("prompts/conventions.md")
        enum_row = next(
            line for line in conventions.splitlines() if line.startswith("| `sub_step` |")
        )
        self.assertIn('"review_reentry"', enum_row)
        self.assertIn("Phase 6 only", enum_row)

    def test_legacy_round_identity_migration_is_unambiguous(self):
        conventions = read("prompts/conventions.md")
        self.assertIn("summaries/round{current_round}_*/", conventions)
        self.assertIn("exactly one", conventions)
        self.assertRegex(
            conventions,
            re.compile(r"zero or multiple.*STOP.*ask", re.IGNORECASE | re.DOTALL),
        )
        self.assertRegex(
            conventions,
            re.compile(
                r"persist.*current_round_short_name.*atomically",
                re.IGNORECASE | re.DOTALL,
            ),
        )


class TestRoundScopedExperimentExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase5 = read("prompts/05_experiment_execution.md")

    def test_round_dir_and_artifacts_are_round_scoped(self):
        self.assertIn(
            "round_dir = round{current_round}_{current_round_short_name}",
            self.phase5,
        )
        self.assertIn(
            "experiment/results/{round_dir}/{exp_id}/", self.phase5
        )
        self.assertIn(
            "experiment/checkpoints/{round_dir}/{exp_id}/", self.phase5
        )
        self.assertIn("experiment/logs/{round_dir}/", self.phase5)
        self.assertIn(
            "experiment/logs/{round_dir}/{exp_id}/attempt_{attempt}_{timestamp}.log",
            self.phase5,
        )
        self.assertIn("immutable", self.phase5.lower())
        self.assertIn("experiment/results/{round_dir}/ALL_COMPLETE", self.phase5)

    def test_project_global_completion_and_unscoped_results_are_forbidden(self):
        self.assertNotIn("experiment/ALL_COMPLETE", self.phase5)
        self.assertNotIn("experiment/results/{exp_id}", self.phase5)

    def test_round_short_name_is_required_before_execution(self):
        self.assertRegex(
            self.phase5,
            re.compile(
                r"current_round_short_name.*nonempty.*before.*execut",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertRegex(
            self.phase5,
            re.compile(r"empty.*STOP", re.IGNORECASE | re.DOTALL),
        )

    def test_resume_requires_exact_seed_independent_config_fingerprint(self):
        self.assertIn("resolved_config", self.phase5)
        self.assertIn("config_fingerprint", self.phase5)
        self.assertRegex(
            self.phase5,
            re.compile(
                r"resume only.*exact.*config_fingerprint.*match",
                re.IGNORECASE | re.DOTALL,
            ),
        )
        self.assertIn("seed-independent", self.phase5)
        self.assertIn("config drift", self.phase5.lower())


class TestReviewReentry(unittest.TestCase):
    def test_phase8_persists_review_reentry_and_round_identity(self):
        phase8 = read("prompts/08_manuscript_review.md")
        self.assertIn('`sub_step`: `"review_reentry"`', phase8)
        self.assertRegex(
            phase8,
            re.compile(
                r"preserve.*current_round.*current_round_short_name",
                re.IGNORECASE | re.DOTALL,
            ),
        )

    def test_phase6_dispatches_and_clears_review_reentry(self):
        phase6 = read("prompts/06_result_analysis.md")
        self.assertIn('sub_step == "review_reentry"', phase6)
        self.assertRegex(
            phase6,
            re.compile(
                r"review_reentry.*(clear|change).*sub_step.*leav",
                re.IGNORECASE | re.DOTALL,
            ),
        )


class TestTerminalProjectStartup(unittest.TestCase):
    def test_entrypoints_stop_terminal_projects_before_phase_dispatch(self):
        for entrypoint in ("AGENTS.md", "CLAUDE.md"):
            with self.subTest(entrypoint=entrypoint):
                text = read(entrypoint)
                ordering = "Check `project_status` before dispatching on `phase_status`"
                self.assertIn(ordering, text)
                self.assertIn("report final artifacts and do not advance", text)
                self.assertIn("report that it is archived and do not mutate or advance", text)
                self.assertLess(text.index(ordering), text.index("- `not_started`"))


class TestRoundIdentityOwnership(unittest.TestCase):
    def test_phase1_initializes_empty_round_short_name(self):
        phase1 = read("prompts/01_interview.md")
        self.assertGreaterEqual(
            phase1.count('`current_round_short_name`: `""`'),
            2,
            "draft and completed interview state must both initialize the field",
        )

    def test_phase3_increments_round_and_clears_short_name(self):
        phase3 = read("prompts/03_research_plan.md")
        self.assertIn("`current_round`: increment by 1", phase3)
        self.assertIn('`current_round_short_name`: `""`', phase3)

    def test_phase4_persists_chosen_short_name(self):
        phase4 = read("prompts/04_experiment_design.md")
        self.assertIn(
            "`current_round_short_name`: the confirmed round `short_name`", phase4
        )

    def test_phase6_sets_or_preserves_round_identity_by_route(self):
        phase6 = read("prompts/06_result_analysis.md")
        self.assertIn(
            'Phase 4 route clears `current_round_short_name` to `""`', phase6
        )
        self.assertIn(
            "direct Phase 5 route sets `current_round_short_name`", phase6
        )
        self.assertIn(
            "Phase 7 and Phase 3 routes preserve `current_round_short_name`", phase6
        )


if __name__ == "__main__":
    unittest.main()
