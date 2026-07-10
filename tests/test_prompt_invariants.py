"""Regression tests for cross-phase prompt and state invariants."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def read(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def between(text, start, end=None):
    """Return prompt text after *start* and before *end*."""
    _, separator, tail = text.partition(start)
    if not separator:
        raise AssertionError(f"missing section start: {start}")
    if end is None:
        return tail
    body, separator, _ = tail.partition(end)
    if not separator:
        raise AssertionError(f"missing section end: {end}")
    return body


def state_line(section, field):
    prefix = f"- `{field}`:"
    return next(
        (line.strip() for line in section.splitlines() if line.strip().startswith(prefix)),
        None,
    )


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
        migration = between(
            conventions,
            "### Legacy round-identity migration",
            "## Round Numbering",
        )
        self.assertIn("summaries/round{current_round}_*/", migration)
        self.assertIn("exactly one", migration)
        self.assertRegex(
            migration,
            re.compile(r"zero or multiple.*STOP.*ask", re.IGNORECASE | re.DOTALL),
        )
        self.assertRegex(
            migration,
            re.compile(
                r"persist.*current_round_short_name.*atomically",
                re.IGNORECASE | re.DOTALL,
            ),
        )

    def test_legacy_migration_distinguishes_missing_from_present_empty(self):
        conventions = read("prompts/conventions.md")
        migration = between(
            conventions,
            "### Legacy round-identity migration",
            "## Round Numbering",
        )
        self.assertIn(
            "Migration applies only when the `current_round_short_name` key is absent",
            migration,
        )
        self.assertIn(
            'If the key is present with value `""`, do not run migration',
            migration,
        )
        self.assertIn("pending Phase 4 naming", migration)
        self.assertNotIn("absent or empty", migration)


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
            "run_dir = {round_dir}/{exp_id}/seed{seed}", self.phase5
        )
        self.assertIn(
            "experiment/results/{run_dir}/", self.phase5
        )
        self.assertIn(
            "experiment/checkpoints/{run_dir}/", self.phase5
        )
        self.assertIn(
            "experiment/logs/{run_dir}/attempt_{attempt}_{timestamp}.log",
            self.phase5,
        )
        self.assertIn("immutable", self.phase5.lower())
        self.assertIn("experiment/results/{round_dir}/ALL_COMPLETE", self.phase5)

    def test_completion_and_failure_markers_are_seed_scoped(self):
        self.assertIn("experiment/results/{run_dir}/COMPLETED", self.phase5)
        self.assertIn("experiment/results/{run_dir}/FAILED", self.phase5)
        self.assertIn("experiment/logs/{run_dir}/current_pid", self.phase5)
        self.assertIn("experiment ID and seed", self.phase5)

    def test_global_and_experiment_only_run_artifacts_are_forbidden(self):
        self.assertNotIn("experiment/ALL_COMPLETE", self.phase5)
        self.assertNotIn("experiment/results/{exp_id}", self.phase5)
        self.assertNotIn(
            "experiment/results/{round_dir}/{exp_id}/COMPLETED", self.phase5
        )
        self.assertNotIn(
            "experiment/results/{round_dir}/{exp_id}/FAILED", self.phase5
        )
        self.assertNotIn(
            "experiment/checkpoints/{round_dir}/{exp_id}/", self.phase5
        )

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

    def test_phase5_migrates_missing_but_not_present_empty_identity(self):
        self.assertIn(
            "If the `current_round_short_name` key is absent, STOP and run the legacy migration",
            self.phase5,
        )
        self.assertIn(
            'If the key is present with value `""`, STOP without migration',
            self.phase5,
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

    def test_phase6_checks_seed_scoped_run_markers(self):
        phase6 = read("prompts/06_result_analysis.md")
        self.assertIn(
            "experiment/results/{round_dir}/*/seed*/COMPLETED", phase6
        )


class TestRoundScopedResultConsumers(unittest.TestCase):
    def test_phase6_producer_and_phase7_consumers_share_round_path(self):
        phase6 = read("prompts/06_result_analysis.md")
        phase7 = read("prompts/07_manuscript_writing.md")
        result_json = (
            "{project_dir}/experiment/results/{round_dir}/comparison_table.json"
        )
        result_md = (
            "{project_dir}/experiment/results/{round_dir}/comparison_table.md"
        )
        self.assertIn(result_json, phase6)
        self.assertIn(result_md, phase6)
        self.assertGreaterEqual(phase7.count(result_json), 2)
        self.assertGreaterEqual(phase7.count(result_md), 1)
        self.assertIn(
            "round_dir = round{current_round}_{current_round_short_name}", phase7
        )

    def test_phase7_has_no_project_global_comparison_table_consumer(self):
        phase7 = read("prompts/07_manuscript_writing.md")
        self.assertNotIn(
            "{project_dir}/experiment/results/comparison_table.json", phase7
        )
        self.assertNotIn(
            "{project_dir}/experiment/results/comparison_table.md", phase7
        )


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
        entry = between(phase6, "## Entry Routing", "## Prerequisites")
        self.assertIn(
            'If `sub_step == "review_reentry"`, the persisted marker proves this is review-driven planning from Phase 8',
            entry,
        )
        self.assertIn(
            "clear or change `sub_step` before leaving re-entry planning",
            entry,
        )

    def test_review_reentry_guard_skips_closed_round_bookkeeping(self):
        phase6 = read("prompts/06_result_analysis.md")
        guard = between(
            phase6,
            "### Review Re-entry Bookkeeping Guard (MANDATORY)",
            "### 6.9 Read the Roadmap",
        )
        required_rules = (
            "Do not move the prior round's Active direction to Completed again.",
            "Do not append a Results Comparison row for the prior round.",
            "Do not re-run abandonment or other normal-analysis closure bookkeeping for the prior round.",
            "Do not write or modify the prior round's `phase6_results.md` or `round_summary.md`.",
            "Preserve the prior round's existing summaries and `phase_history` entries.",
            "May re-prioritize Pending directions and add new Pending directions from `review_synthesis.md`.",
        )
        for rule in required_rules:
            with self.subTest(rule=rule):
                self.assertIn(rule, guard)

    def test_review_reentry_guards_roadmap_and_summary_sections(self):
        phase6 = read("prompts/06_result_analysis.md")
        roadmap_update = between(
            phase6,
            "### 6.10 Update Roadmap",
            "### 6.11 Present Round Options",
        )
        round_summary = between(
            phase6,
            "### 6.13 Write Round Summary",
            "## Roadmap Initialization",
        )
        phase_summary = between(phase6, "## Phase Summary", "## State Update")
        self.assertIn(
            "Normal analysis only — skip in `review_reentry`", roadmap_update
        )
        self.assertIn(
            "If `sub_step == \"review_reentry\"`, skip this entire section",
            round_summary,
        )
        self.assertIn(
            "If `sub_step == \"review_reentry\"`, do not write or modify either prior-round summary file",
            phase_summary,
        )

    def test_review_reentry_state_routes_do_not_reclose_prior_round(self):
        phase6 = read("prompts/06_result_analysis.md")
        state_update = between(phase6, "## State Update")
        self.assertIn(
            "For `review_reentry`, never move the prior round to Completed again",
            state_update,
        )
        self.assertIn(
            "never append another `round_closed` or `phase_completed` event for it",
            state_update,
        )

    def test_review_reentry_round_activation_is_route_specific(self):
        phase6 = read("prompts/06_result_analysis.md")
        choice = between(
            phase6,
            "### 6.12 Update Roadmap After User's Choice",
            '### When to set `sub_step: "refinement"`',
        )
        self.assertIn(
            "Reserve and activate `current_round + 1` only for a Phase 4 or direct Phase 5 route.",
            choice,
        )
        self.assertIn(
            "A Phase 7 route creates no new round and no Active next-round entry.",
            choice,
        )
        self.assertIn(
            "A Phase 3 route creates no Active experimental round during re-entry planning",
            choice,
        )
        self.assertNotIn(
            "treat the choice as the next round (`current_round + 1`)", choice
        )

    def test_review_reentry_state_routes_match_activation_ownership(self):
        phase6 = read("prompts/06_result_analysis.md")
        phase4 = between(
            phase6,
            "**If proceeding to another round (Phase 4):**",
            "**If proceeding directly to Phase 5",
        )
        phase5 = between(
            phase6,
            "**If proceeding directly to Phase 5",
            "**If proceeding to manuscript (Phase 7):**",
        )
        phase7 = between(
            phase6,
            "**If proceeding to manuscript (Phase 7):**",
            "**If returning to Phase 3 (fundamental rethink):**",
        )
        phase3 = between(
            phase6,
            "**If returning to Phase 3 (fundamental rethink):**",
        )
        self.assertIn(
            "Reserve the incremented round and mark the chosen direction Active",
            phase4,
        )
        self.assertIn(
            "Reserve the incremented round and mark the chosen direction Active",
            phase5,
        )
        self.assertIn(
            "No new round is reserved and no Active next-round entry is created",
            phase7,
        )
        self.assertIn(
            "Do not reserve or activate a new experimental round during re-entry planning",
            phase3,
        )


class TestCanonicalProvenanceAndPidSafety(unittest.TestCase):
    def test_phase5_requires_strict_collection_and_identity_scoped_aggregation(self):
        phase5 = read("prompts/05_experiment_execution.md")
        result_contract = between(
            phase5,
            "## Experiment Result File Convention",
            "## Checkpoint and Marker Configuration Contract",
        )
        self.assertRegex(result_contract, r"rejects the entire\s+file")
        self.assertIn("non-finite", result_contract)
        self.assertIn(
            "(round, experiment_id, config_fingerprint, method, group)",
            result_contract,
        )
        self.assertIn("duplicate seeded identity", result_contract)
        self.assertIn("suppresses that aggregate", result_contract)
        self.assertIn("--fail-on-warnings", result_contract)

    def test_failure_logs_use_seed_scoped_immutable_attempt_paths(self):
        conventions = read("prompts/conventions.md")
        recovery = between(conventions, "## Error Recovery", "## Per-Project Paths")
        self.assertIn(
            "{project_dir}/experiment/logs/{run_dir}/attempt_{attempt}_{timestamp}.log",
            recovery,
        )
        self.assertNotIn(
            "experiment/logs/round{current_round}_{current_round_short_name}/",
            recovery,
        )

    def test_phase6_meta_contract_lists_canonical_exact_fields(self):
        phase5 = read("prompts/05_experiment_execution.md")
        phase6 = read("prompts/06_result_analysis.md")
        meta = between(phase6, "**`_meta` requirement:**", "After generating")
        canonical_fields = (
            "`experiment_id`, `script`, `log_file`, `timestamp`, "
            "`resolved_config`, `config_fingerprint`, `round`, and `seed`"
        )
        self.assertIn(canonical_fields, meta)
        self.assertIn("`seed` is always required and must never be omitted", meta)
        self.assertIn(
            'Per-run files use a nonnegative integer; aggregated files use `seed: "aggregate"`',
            meta,
        )
        self.assertIn(
            "`resolved_config.contributing_seeds` must be a nonempty list of nonnegative integers",
            meta,
        )
        self.assertNotIn("may be omitted", meta)
        self.assertNotIn("timestamp, config, round", meta)
        self.assertIn('"experiment_id": "E01"', phase5)

    def test_phase5_and_plans_require_explicit_seed_metadata(self):
        phase5 = read("prompts/05_experiment_execution.md")
        design = read("docs/plans/2026-07-10-core-gates-design.md")
        plan = read("docs/plans/2026-07-10-core-gates.md")
        self.assertIn("`_meta.seed` is always required; never omit it", phase5)
        self.assertIn('"seed": "aggregate"', phase5)
        self.assertIn('"contributing_seeds": [42, 123, 456]', phase5)
        for document in (design, plan):
            with self.subTest(document=document[:40]):
                self.assertIn("`_meta.seed` is always required", document)
                self.assertIn('`seed: "aggregate"`', document)
                self.assertIn("`resolved_config.contributing_seeds`", document)
                self.assertNotIn("seed` is optional", document)

    def test_phase6_evidence_examples_include_seed_identity(self):
        phase6 = read("prompts/06_result_analysis.md")
        evidence_paths = re.findall(r"`([^`]*eval_results\.json)`", phase6)
        self.assertGreaterEqual(len(evidence_paths), 4)
        for path in evidence_paths:
            with self.subTest(path=path):
                self.assertRegex(path, r"/seed(?:\{seed\}|\*)/")

    def test_phase5_pid_examples_validate_and_quote_pids(self):
        phase5 = read("prompts/05_experiment_execution.md")
        self.assertNotIn("kill $(cat", phase5)
        self.assertNotRegex(phase5, r"kill -0\s+\$\(cat")
        self.assertNotIn("PID=$(cat", phase5)
        self.assertIn('IFS= read -r PID < "$PIDFILE"', phase5)
        self.assertIn('[[ "$PID" =~ ^[1-9][0-9]*$ ]]', phase5)
        self.assertIn('kill -0 "$PID"', phase5)
        self.assertIn('kill "$PID"', phase5)
        self.assertGreaterEqual(
            phase5.count('[ -r "$PIDFILE" ] || continue'),
            2,
            "both PID glob loops must skip unreadable or unmatched paths quietly",
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

    def test_phase6_every_exit_route_explicitly_updates_sub_step(self):
        phase6 = read("prompts/06_result_analysis.md")
        phase4 = between(
            phase6,
            "**If proceeding to another round (Phase 4):**",
            "**If proceeding directly to Phase 5",
        )
        phase5 = between(
            phase6,
            "**If proceeding directly to Phase 5",
            "**If proceeding to manuscript (Phase 7):**",
        )
        phase7 = between(
            phase6,
            "**If proceeding to manuscript (Phase 7):**",
            "**If returning to Phase 3 (fundamental rethink):**",
        )
        phase3 = between(
            phase6,
            "**If returning to Phase 3 (fundamental rethink):**",
        )

        phase4_sub_step = state_line(phase4, "sub_step")
        self.assertIsNotNone(phase4_sub_step)
        self.assertIn("`null`", phase4_sub_step)
        self.assertIn('`"refinement"`', phase4_sub_step)
        self.assertEqual(state_line(phase5, "sub_step"), "- `sub_step`: `null`")
        self.assertEqual(state_line(phase7, "sub_step"), "- `sub_step`: `null`")
        self.assertEqual(state_line(phase3, "sub_step"), "- `sub_step`: `null`")


if __name__ == "__main__":
    unittest.main()
