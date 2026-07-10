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


def complete_meta(experiment_id="E01", seed=0, fingerprint="cfg-v1", round_=1):
    return {
        "experiment_id": experiment_id,
        "config_fingerprint": fingerprint,
        "script": "scripts/eval.py",
        "log_file": "logs/eval.log",
        "timestamp": "2026-07-10T00:00:00Z",
        "resolved_config": {"model": experiment_id},
        "round": round_,
        "seed": seed,
    }


RESULT_A = {
    "_meta": complete_meta(),
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
    """Malformed or incomplete provenance must never yield claims."""

    def test_missing_meta_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round1_eval.json", {"accuracy": 0.5})
            collected = cr.collect_results(tdir)
            self.assertTrue(
                any("_meta" in w for w in collected["warnings"]),
                collected["warnings"],
            )
            self.assertEqual(collected["entries"], [])

    def test_non_dict_meta_is_rejected_without_hiding_valid_files(self):
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
            self.assertEqual(len(collected["entries"]), 1)

    def test_every_required_meta_field_is_enforced(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            required = set(complete_meta())
            for index, missing in enumerate(sorted(required)):
                meta = complete_meta(experiment_id=f"E{index:02d}")
                del meta[missing]
                write_json(
                    tdir / f"missing_{missing}.json",
                    {"_meta": meta, "accuracy": 0.5},
                )

            collected = cr.collect_results(tdir)
            self.assertEqual(collected["entries"], [])
            for missing in required:
                self.assertTrue(
                    any(missing in warning for warning in collected["warnings"]),
                    (missing, collected["warnings"]),
                )

    def test_invalid_rounds_and_seeds_are_rejected(self):
        invalid_cases = [
            ("round_zero", {"round": 0}),
            ("round_negative", {"round": -1}),
            ("round_string", {"round": "1"}),
            ("round_bool", {"round": True}),
            ("seed_negative", {"seed": -1}),
            ("seed_string", {"seed": "0"}),
            ("seed_bool", {"seed": False}),
            ("seed_null", {"seed": None}),
        ]
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for name, override in invalid_cases:
                meta = complete_meta(experiment_id=name)
                meta.update(override)
                write_json(tdir / f"{name}.json", {"_meta": meta, "accuracy": 0.5})

            collected = cr.collect_results(tdir)
            self.assertEqual(collected["entries"], [])
            self.assertEqual(len(collected["warnings"]), len(invalid_cases))

    def test_required_meta_types_are_enforced(self):
        invalid_cases = [
            ("experiment_id", " "),
            ("config_fingerprint", 123),
            ("script", None),
            ("log_file", []),
            ("timestamp", False),
            ("resolved_config", "model=E01"),
        ]
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for index, (field, value) in enumerate(invalid_cases):
                meta = complete_meta(experiment_id=f"E{index}")
                meta[field] = value
                write_json(
                    tdir / f"invalid_{field}.json",
                    {"_meta": meta, "accuracy": 0.5},
                )

            collected = cr.collect_results(tdir)
            self.assertEqual(collected["entries"], [])
            self.assertEqual(len(collected["warnings"]), len(invalid_cases))


class TestNoPathInference(unittest.TestCase):
    def test_round_is_not_inferred_from_path(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            meta = complete_meta()
            del meta["round"]
            write_json(
                tdir / "round12" / "seed0.json",
                {"_meta": meta, "accuracy": 0.5},
            )
            collected = cr.collect_results(tdir)
            self.assertEqual(collected["entries"], [])
            self.assertTrue(
                any("_meta.round" in warning for warning in collected["warnings"]),
                collected["warnings"],
            )


class TestSeedAggregation(unittest.TestCase):
    """Bug 12: mean/std across seeds, as the docstring promises."""

    def _make_seed_files(self, tdir):
        for seed, acc in [(0, 0.90), (1, 0.92), (2, 0.94)]:
            write_json(tdir / f"round1_seed{seed}.json", {
                "_meta": complete_meta(seed=seed),
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

    def test_seed_is_not_inferred_from_filename(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for seed, acc in [(1, 0.5), (2, 0.7)]:
                meta = complete_meta(round_=2, seed=seed)
                del meta["seed"]
                write_json(tdir / f"round2_eval_seed_{seed}.json", {
                    "_meta": meta,
                    "accuracy": acc,
                })
            collected = cr.collect_results(tdir)
            self.assertEqual(collected["entries"], [])
            self.assertEqual(collected["aggregates"], [])
            self.assertEqual(len(collected["warnings"]), 2)

    def test_experiments_and_configurations_are_aggregated_separately(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            cases = [
                ("E01", "cfg-a", 0, 0.90),
                ("E01", "cfg-a", 1, 0.80),
                ("E02", "cfg-b", 0, 0.20),
                ("E02", "cfg-b", 1, 0.10),
            ]
            for experiment_id, fingerprint, seed, accuracy in cases:
                write_json(
                    tdir / f"{experiment_id}_{seed}.json",
                    {
                        "_meta": complete_meta(experiment_id, seed, fingerprint),
                        "accuracy": accuracy,
                    },
                )

            collected = cr.collect_results(tdir)
            aggregates = {
                (item["experiment_id"], item["config_fingerprint"]): item
                for item in collected["aggregates"]
            }
            self.assertEqual(set(aggregates), {("E01", "cfg-a"), ("E02", "cfg-b")})
            self.assertAlmostEqual(
                aggregates[("E01", "cfg-a")]["metrics"]["accuracy"]["mean"], 0.85
            )
            self.assertAlmostEqual(
                aggregates[("E02", "cfg-b")]["metrics"]["accuracy"]["mean"], 0.15
            )

    def test_duplicate_seed_identity_warns_and_suppresses_aggregate(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for filename, seed, accuracy in [
                ("first_seed0.json", 0, 0.1),
                ("duplicate_seed0.json", 0, 0.9),
                ("seed1.json", 1, 0.5),
            ]:
                write_json(
                    tdir / filename,
                    {"_meta": complete_meta(seed=seed), "accuracy": accuracy},
                )

            collected = cr.collect_results(tdir)
            self.assertEqual(len(collected["entries"]), 3)
            self.assertEqual(collected["aggregates"], [])
            self.assertTrue(
                any("duplicate" in warning.lower() for warning in collected["warnings"]),
                collected["warnings"],
            )

    def test_metric_filter_cannot_hide_duplicate_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(
                tdir / "first_seed0.json",
                {"_meta": complete_meta(seed=0), "accuracy": 0.1},
            )
            write_json(
                tdir / "duplicate_seed0.json",
                {"_meta": complete_meta(seed=0), "loss": 0.2},
            )
            write_json(
                tdir / "seed1.json",
                {"_meta": complete_meta(seed=1), "accuracy": 0.5},
            )

            collected = cr.collect_results(tdir, metric_keys=["accuracy"])
            self.assertEqual(collected["aggregates"], [])
            self.assertTrue(
                any("duplicate" in warning.lower() for warning in collected["warnings"]),
                collected["warnings"],
            )

    def test_aggregate_input_is_an_entry_but_not_a_seed_source(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            aggregate_meta = complete_meta(seed="aggregate")
            aggregate_meta["resolved_config"]["contributing_seeds"] = [0, 1]
            write_json(
                tdir / "already_aggregated.json",
                {"_meta": aggregate_meta, "accuracy_mean": 0.8},
            )
            write_json(
                tdir / "seed0.json",
                {"_meta": complete_meta(seed=0), "accuracy": 0.7},
            )
            write_json(
                tdir / "seed1.json",
                {"_meta": complete_meta(seed=1), "accuracy": 0.9},
            )

            collected = cr.collect_results(tdir)
            self.assertIn("aggregate", {entry["seed"] for entry in collected["entries"]})
            self.assertEqual(len(collected["aggregates"]), 1)
            self.assertEqual(collected["aggregates"][0]["seeds"], [0, 1])

    def test_aggregate_seed_requires_contributing_seeds(self):
        invalid_values = [None, [], [0, -1], [0, True], ["0", 1]]
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for index, value in enumerate(invalid_values):
                meta = complete_meta(experiment_id=f"E{index}", seed="aggregate")
                if value is not None:
                    meta["resolved_config"]["contributing_seeds"] = value
                write_json(
                    tdir / f"invalid_aggregate_{index}.json",
                    {"_meta": meta, "accuracy_mean": 0.8},
                )

            collected = cr.collect_results(tdir)
            self.assertEqual(collected["entries"], [])
            self.assertEqual(len(collected["warnings"]), len(invalid_values))

    def test_markdown_includes_aggregates(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            self._make_seed_files(tdir)
            collected = cr.collect_results(tdir)
            md = cr.format_markdown(collected)
            self.assertIn("Seed Aggregates", md)
            self.assertIn("E01", md)
            self.assertIn("cfg-v1", md)
            self.assertIn("0.9200", md)


class TestCountsAndFlags(unittest.TestCase):
    """Bug 15: files_with_metrics counts files; --fail-on-warnings enforceable."""

    def test_files_with_metrics_counts_files_not_entries(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            # One file that yields a method table AND top-level metrics: 1 file,
            # multiple entries.
            write_json(tdir / "round1_eval.json", {
                "_meta": complete_meta(),
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

    def test_duplicate_warning_is_enforced_by_cli_gate(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            for filename, seed in [("seed0_a.json", 0), ("seed0_b.json", 0)]:
                write_json(
                    tdir / filename,
                    {"_meta": complete_meta(seed=seed), "accuracy": 0.5},
                )
            argv = ["collect_results.py", str(tdir), "--fail-on-warnings"]
            with mock.patch.object(sys, "argv", argv), \
                    contextlib.redirect_stdout(io.StringIO()), \
                    contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    cr.main()
            self.assertNotEqual(ctx.exception.code, 0)

    def test_configured_custom_output_is_excluded_on_rerun(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "valid.json", RESULT_A)
            output_path = tdir / "my_custom_export.json"
            argv = [
                "collect_results.py",
                str(tdir),
                "--output-json",
                str(output_path),
                "--fail-on-warnings",
            ]
            for _ in range(2):
                with mock.patch.object(sys, "argv", argv), \
                        contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    cr.main()
            exported = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(exported["files_scanned"], 1)
            self.assertEqual(exported["warnings"], [])


class TestHappyPath(unittest.TestCase):
    def test_method_rows_and_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "round3_methods.json", {
                "_meta": complete_meta(round_=3),
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


class TestMalformedInputs(unittest.TestCase):
    def test_empty_non_object_nan_and_no_metric_files_warn_and_skip(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "empty.json").write_text("", encoding="utf-8")
            (tdir / "list.json").write_text("[]", encoding="utf-8")
            (tdir / "nan.json").write_text(
                json.dumps({"_meta": complete_meta(experiment_id="nan")})[:-1]
                + ', "accuracy": NaN}',
                encoding="utf-8",
            )
            write_json(
                tdir / "no_metrics.json",
                {"_meta": complete_meta(experiment_id="empty-metrics"), "notes": "done"},
            )

            collected = cr.collect_results(tdir)
            self.assertEqual(collected["files_scanned"], 4)
            self.assertEqual(collected["entries"], [])
            self.assertEqual(len(collected["warnings"]), 4)

    def test_json_named_directory_and_read_errors_warn_without_crashing(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "directory.json").mkdir()
            write_json(tdir / "unreadable.json", {"_meta": complete_meta(), "accuracy": 0.5})

            original_read_text = Path.read_text

            def fail_one(path, *args, **kwargs):
                if path.name == "unreadable.json":
                    raise OSError("simulated read failure")
                return original_read_text(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", fail_one):
                collected = cr.collect_results(tdir)

            self.assertEqual(collected["files_scanned"], 2)
            self.assertEqual(collected["entries"], [])
            self.assertEqual(len(collected["warnings"]), 2)

    def test_metric_filter_that_matches_nothing_is_not_a_malformed_warning(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(
                tdir / "valid.json",
                {"_meta": complete_meta(), "accuracy": 0.9},
            )
            collected = cr.collect_results(tdir, metric_keys=["loss"])
            self.assertEqual(collected["entries"], [])
            self.assertEqual(collected["warnings"], [])

    def test_reserved_outputs_are_not_scanned_but_renamed_output_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            write_json(tdir / "valid.json", RESULT_A)
            first = cr.collect_results(tdir)
            write_json(tdir / "comparison_table.json", first)
            write_json(tdir / "renamed.json", first)

            collected = cr.collect_results(tdir)
            self.assertEqual(collected["files_scanned"], 2)
            self.assertEqual({entry["file"] for entry in collected["entries"]}, {"valid.json"})
            self.assertTrue(
                any("collect_results.py output" in warning for warning in collected["warnings"]),
                collected["warnings"],
            )


if __name__ == "__main__":
    unittest.main()
