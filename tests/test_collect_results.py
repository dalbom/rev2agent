"""Tests for scripts/collect_results.py."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import collect_results as cr  # noqa: E402


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


RESULT_A = {
    "_meta": {"round": 1, "script": "eval.py", "timestamp": "2026-01-01T00:00:00Z"},
    "accuracy": 0.91,
    "loss": 0.10,
}


class TestSkipOwnOutput(unittest.TestCase):
    """Bug 11: the collector must not re-ingest its own comparison table."""

    def test_comparison_table_filename_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round1_eval.json", RESULT_A)
            # Simulate a previous run's output living in the scanned dir
            collected_prev = cr.collect_results(tdir)
            write_json(tdir / "comparison_table.json", collected_prev)
            write_json(tdir / "comparison_table_v2.json", collected_prev)

            collected = cr.collect_results(tdir)
            files = {e["file"] for e in collected["entries"]}
            self.assertEqual(files, {"round1_eval.json"})

    def test_output_shaped_json_skipped_even_if_renamed(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round1_eval.json", RESULT_A)
            prev = cr.collect_results(tdir)
            write_json(tdir / "summary_export.json", prev)

            collected = cr.collect_results(tdir)
            files = {e["file"] for e in collected["entries"]}
            self.assertEqual(files, {"round1_eval.json"})

    def test_idempotent_rerun(self):
        """Running twice with the output written into the dir must be stable."""
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round1_eval.json", RESULT_A)
            first = cr.collect_results(tdir)
            write_json(tdir / "comparison_table.json", first)
            second = cr.collect_results(tdir)
            self.assertEqual(first["entries"], second["entries"])


class TestMetaHandling(unittest.TestCase):
    """Bug 13: warn on missing _meta; survive non-dict _meta."""

    def test_missing_meta_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round1_eval.json", {"accuracy": 0.5})
            collected = cr.collect_results(tdir)
            self.assertTrue(
                any("_meta" in w for w in collected["warnings"]),
                collected["warnings"],
            )
            # The metrics are still collected
            self.assertEqual(len(collected["entries"]), 1)

    def test_non_dict_meta_degrades_to_warning(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round1_eval.json",
                       {"_meta": "not-a-dict", "accuracy": 0.5})
            write_json(tdir / "round2_eval.json", RESULT_A)
            collected = cr.collect_results(tdir)  # must not raise
            self.assertTrue(
                any("_meta" in w for w in collected["warnings"]),
                collected["warnings"],
            )
            # Both files still produce entries
            self.assertEqual(len(collected["entries"]), 2)


class TestInferRound(unittest.TestCase):
    """Bug 14: 'playground2' must not be parsed as round 2."""

    def test_playground_not_a_round(self):
        self.assertIsNone(cr.infer_round_from_path(Path("playground2/results.json")))
        self.assertIsNone(cr.infer_round_from_path(Path("background5.json")))

    def test_real_round_names(self):
        self.assertEqual(cr.infer_round_from_path(Path("round5_combined.json")), 5)
        self.assertEqual(
            cr.infer_round_from_path(Path("results/round12_ablation/eval.json")), 12)
        self.assertEqual(
            cr.infer_round_from_path(Path("exp_round3.json")), 3)


class TestSeedAggregation(unittest.TestCase):
    """Bug 12: mean/std across seeds, as the docstring promises."""

    def _make_seed_files(self, tdir):
        for seed, acc in [(0, 0.90), (1, 0.92), (2, 0.94)]:
            write_json(tdir / f"round1_seed{seed}.json", {
                "_meta": {"round": 1, "seed": seed},
                "accuracy": acc,
            })

    def test_aggregates_present(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            self._make_seed_files(tdir)
            collected = cr.collect_results(tdir)
            self.assertIn("aggregates", collected)
            aggs = collected["aggregates"]
            self.assertEqual(len(aggs), 1)
            agg = aggs[0]
            self.assertEqual(agg["round"], 1)
            self.assertEqual(agg["n_seeds"], 3)
            acc = agg["metrics"]["accuracy"]
            self.assertAlmostEqual(acc["mean"], 0.92, places=6)
            self.assertAlmostEqual(acc["std"], 0.02, places=6)
            self.assertEqual(acc["n"], 3)

    def test_per_seed_rows_kept_and_labeled(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            self._make_seed_files(tdir)
            collected = cr.collect_results(tdir)
            seeds = sorted(e.get("seed") for e in collected["entries"])
            self.assertEqual(seeds, [0, 1, 2])

    def test_seed_inferred_from_filename(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for seed, acc in [(1, 0.5), (2, 0.7)]:
                write_json(tdir / f"round2_eval_seed_{seed}.json", {
                    "_meta": {"round": 2},
                    "accuracy": acc,
                })
            collected = cr.collect_results(tdir)
            aggs = collected["aggregates"]
            self.assertEqual(len(aggs), 1)
            self.assertEqual(aggs[0]["n_seeds"], 2)
            self.assertAlmostEqual(aggs[0]["metrics"]["accuracy"]["mean"], 0.6)

    def test_markdown_includes_aggregates(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            self._make_seed_files(tdir)
            collected = cr.collect_results(tdir)
            md = cr.format_markdown(collected)
            self.assertIn("Seed Aggregates", md)
            self.assertIn("0.9200", md)


class TestCountsAndFlags(unittest.TestCase):
    """Bug 15: files_with_metrics counts files; --fail-on-warnings enforceable."""

    def test_files_with_metrics_counts_files_not_entries(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            # One file that yields a method table AND top-level metrics: 1 file,
            # multiple entries.
            write_json(tdir / "round1_eval.json", {
                "_meta": {"round": 1},
                "overall_accuracy": 0.9,
                "baselines": [
                    {"name": "A", "accuracy": 0.8},
                    {"name": "B", "accuracy": 0.85},
                ],
            })
            collected = cr.collect_results(tdir)
            self.assertEqual(collected["files_with_metrics"], 1)
            self.assertEqual(collected["entries_extracted"],
                             len(collected["entries"]))
            self.assertGreater(collected["entries_extracted"], 1)

    def test_fail_on_warnings_exit_code(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round1_eval.json", {"accuracy": 0.5})  # no _meta
            argv = ["collect_results.py", str(tdir), "--fail-on-warnings"]
            buf = io.StringIO()
            with mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(buf):
                with self.assertRaises(SystemExit) as ctx:
                    cr.main()
            self.assertNotEqual(ctx.exception.code, 0)

    def test_no_fail_without_flag(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round1_eval.json", {"accuracy": 0.5})
            argv = ["collect_results.py", str(tdir)]
            buf = io.StringIO()
            with mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(buf):
                cr.main()  # should not raise SystemExit


class TestHappyPath(unittest.TestCase):
    def test_method_rows_and_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round3_methods.json", {
                "_meta": {"round": 3},
                "baselines_and_ablations": [
                    {"name": "Baseline A", "accuracy": 0.95, "loss": 0.12},
                    {"name": "Ours", "accuracy": 0.97, "loss": 0.08},
                ],
            })
            collected = cr.collect_results(tdir)
            methods = {e["method"] for e in collected["entries"] if e["method"]}
            self.assertEqual(methods, {"Baseline A", "Ours"})
            md = cr.format_markdown(collected)
            self.assertIn("Round 3", md)
            self.assertIn("| Ours |", md)
            self.assertIn("0.9700", md)


if __name__ == "__main__":
    unittest.main()
