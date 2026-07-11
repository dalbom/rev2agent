#!/usr/bin/env python3
"""
Experiment Result Collector

Scans experiment result directories for JSON files, extracts metrics,
computes mean +/- std across seeds, and outputs structured comparison
tables in both Markdown and JSON formats.

Every number in the output includes provenance (source file paths),
so downstream consumers never need to cite from memory.

Usage:
    python collect_results.py experiment/results/
    python collect_results.py experiment/results/ --output-md comparison.md --output-json comparison.json
    python collect_results.py experiment/results/ --metric-keys cls_auc_mean,recon_ssim

Requires only Python 3.10+ stdlib (no external dependencies).
"""

import sys
import argparse
import hashlib
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Top-level keys that identify this script's own output (comparison table).
# Such files must never be re-ingested as experiment results.
_OUTPUT_SIGNATURE_KEYS = {"results_dir", "files_scanned", "entries"}


def is_sha256_fingerprint(value: Any) -> bool:
    """Return whether *value* uses the canonical ``sha256:<hex>`` wire format."""
    prefix = "sha256:"
    return (
        isinstance(value, str)
        and value.startswith(prefix)
        and len(value) == len(prefix) + 64
        and all(char in "0123456789abcdef" for char in value[len(prefix):])
    )


def compute_evidence_contract_fingerprint(contract: Dict[str, Any]) -> str:
    """Return the canonical fingerprint of an embedded Evidence Contract."""
    canonical_json = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_config_fingerprint(
    resolved_config: Dict[str, Any], *, aggregate: bool = False
) -> str:
    """Return the canonical SHA-256 fingerprint required by Phase 5.

    ``seed`` is run identity rather than configuration identity. Aggregate
    files additionally carry ``contributing_seeds`` as provenance, so that
    field is excluded only for aggregate artifacts.
    """
    canonical_config = dict(resolved_config)
    canonical_config.pop("seed", None)
    if aggregate:
        canonical_config.pop("contributing_seeds", None)
    canonical_json = json.dumps(
        canonical_config,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def is_own_output(data: Any) -> bool:
    """Return True if parsed JSON looks like this script's own output."""
    return (
        isinstance(data, dict)
        and "_meta" not in data
        and _OUTPUT_SIGNATURE_KEYS <= set(data.keys())
    )


def find_result_files(
    results_dir: Path,
    excluded_paths: Optional[List[Path]] = None,
) -> List[Path]:
    """
    Find all JSON candidate paths under results_dir.

    Excludes only explicitly configured output paths. Content validation
    happens later so empty, unreadable, broken, non-file, and output-shaped
    candidates are counted and reported rather than hidden by their names.
    """
    excluded = {Path(os.path.abspath(path)) for path in (excluded_paths or [])}
    json_files = sorted(results_dir.rglob("*.json"))
    return [
        path for path in json_files
        if Path(os.path.abspath(path)) not in excluded
    ]


def extract_metrics_flat(data: Dict[str, Any], prefix: str = "") -> Dict[str, float]:
    """
    Recursively extract all numeric leaf values from a nested dict.
    Returns {dotted.key.path: value}.
    Skips list values (handled separately by extract_method_rows).
    """
    metrics = {}
    for key, val in data.items():
        if key.startswith("_"):
            continue
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(val, int) and not isinstance(val, bool):
            metrics[full_key] = val
        elif isinstance(val, float):
            if math.isfinite(val):
                metrics[full_key] = val
        elif isinstance(val, dict):
            metrics.update(extract_metrics_flat(val, full_key))
        # Lists are handled by extract_method_rows
    return metrics


def extract_method_rows(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Detect arrays of method-result dicts and expand each element as a row.

    Looks for top-level or nested values that are lists of dicts with a
    "name" field and at least one numeric metric. Common pattern:

        {"baselines_and_ablations": [
            {"name": "Baseline A", "accuracy": 0.95, "loss": 0.12},
            {"name": "Ours", "accuracy": 0.97, "loss": 0.08},
        ]}

    Returns list of {"method": str, "group": str, "metrics": {key: float}}.
    """
    rows = []
    for key, val in data.items():
        if key.startswith("_"):
            continue
        if isinstance(val, list):
            for item in val:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", item.get("method", item.get("label")))
                if not name:
                    continue
                metrics = extract_metrics_flat(
                    {k: v for k, v in item.items() if k not in ("name", "method", "label")}
                )
                if metrics:
                    rows.append({"method": str(name), "group": key, "metrics": metrics})
        elif isinstance(val, dict):
            # Check nested dicts for arrays
            for subkey, subval in val.items():
                if isinstance(subval, list):
                    sub_data = {subkey: subval}
                    sub_rows = extract_method_rows(sub_data)
                    for r in sub_rows:
                        r["group"] = f"{key}.{r['group']}"
                    rows.extend(sub_rows)
    return rows


def extract_meta(data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Extract and validate the mandatory Phase 5 provenance metadata.

    Returns ``(meta, errors)``. Callers must reject a result whenever errors
    are present; provenance is never inferred from file names or result data.
    """
    if "_meta" not in data:
        return {}, ["missing _meta (mandatory per Phase 5 convention)"]

    meta = data["_meta"]
    if not isinstance(meta, dict):
        return {}, [f"_meta must be an object (got {type(meta).__name__})"]

    errors: List[str] = []
    required = (
        "experiment_id",
        "evidence_contract",
        "evidence_contract_id",
        "evidence_contract_fingerprint",
        "outcome_id",
        "analysis_protocol_id",
        "config_fingerprint",
        "script",
        "log_file",
        "timestamp",
        "resolved_config",
        "round",
        "seed",
    )
    for field in required:
        if field not in meta:
            errors.append(f"_meta.{field} is required")

    for field in (
        "experiment_id",
        "evidence_contract_id",
        "evidence_contract_fingerprint",
        "outcome_id",
        "analysis_protocol_id",
        "config_fingerprint",
        "script",
        "log_file",
        "timestamp",
    ):
        if field in meta and (
            not isinstance(meta[field], str) or not meta[field].strip()
        ):
            errors.append(f"_meta.{field} must be a nonempty string")

    contract_fingerprint = meta.get("evidence_contract_fingerprint")
    if (
        "evidence_contract_fingerprint" in meta
        and isinstance(contract_fingerprint, str)
        and bool(contract_fingerprint.strip())
        and not is_sha256_fingerprint(contract_fingerprint)
    ):
        errors.append(
            "_meta.evidence_contract_fingerprint must use "
            "sha256:<64 lowercase hex characters>"
        )

    contract = meta.get("evidence_contract")
    if "evidence_contract" in meta and not isinstance(contract, dict):
        errors.append("_meta.evidence_contract must be an object")
    elif isinstance(contract, dict):
        contract_id = contract.get("evidence_contract_id")
        meta_contract_id = meta.get("evidence_contract_id")
        if (
            isinstance(meta_contract_id, str)
            and bool(meta_contract_id.strip())
            and contract_id != meta_contract_id
        ):
            errors.append(
                "_meta.evidence_contract_id must match "
                "_meta.evidence_contract.evidence_contract_id"
            )

        expected_contract_fingerprint = compute_evidence_contract_fingerprint(contract)
        if (
            is_sha256_fingerprint(contract_fingerprint)
            and contract_fingerprint != expected_contract_fingerprint
        ):
            errors.append(
                "_meta.evidence_contract_fingerprint mismatch: expected SHA-256 "
                "of canonical _meta.evidence_contract"
            )

        declared_outcomes = contract.get("outcomes")
        declared_outcome_ids = set()
        if isinstance(declared_outcomes, list):
            declared_outcome_ids = {
                outcome.get("outcome_id")
                for outcome in declared_outcomes
                if isinstance(outcome, dict)
            }
        meta_outcome_id = meta.get("outcome_id")
        if (
            isinstance(meta_outcome_id, str)
            and bool(meta_outcome_id.strip())
            and meta_outcome_id not in declared_outcome_ids
        ):
            errors.append(
                "_meta.outcome_id must name an outcome declared in "
                "_meta.evidence_contract.outcomes"
            )

    resolved_config = meta.get("resolved_config")
    if "resolved_config" in meta and not isinstance(resolved_config, dict):
        errors.append("_meta.resolved_config must be an object")

    round_number = meta.get("round")
    if "round" in meta and (
        not isinstance(round_number, int)
        or isinstance(round_number, bool)
        or round_number <= 0
    ):
        errors.append("_meta.round must be a positive integer")

    if "seed" in meta:
        seed = meta["seed"]
        if seed == "aggregate":
            contributing = (
                resolved_config.get("contributing_seeds")
                if isinstance(resolved_config, dict)
                else None
            )
            valid_contributing = (
                isinstance(contributing, list)
                and bool(contributing)
                and all(
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and value >= 0
                    for value in contributing
                )
            )
            if not valid_contributing:
                errors.append(
                    "_meta.resolved_config.contributing_seeds must be a "
                    "nonempty list of nonnegative integers for aggregate results"
                )
        elif (
            not isinstance(seed, int)
            or isinstance(seed, bool)
            or seed < 0
        ):
            errors.append(
                '_meta.seed must be a nonnegative integer or "aggregate"'
            )

    fingerprint = meta.get("config_fingerprint")
    if (
        isinstance(resolved_config, dict)
        and isinstance(fingerprint, str)
        and fingerprint.strip()
    ):
        expected_fingerprint = compute_config_fingerprint(
            resolved_config, aggregate=meta.get("seed") == "aggregate"
        )
        if fingerprint != expected_fingerprint:
            errors.append(
                "_meta.config_fingerprint mismatch: expected SHA-256 of "
                "canonical _meta.resolved_config"
            )

    return meta, errors


def reject_json_constant(value: str) -> None:
    """Reject NaN and infinities, which are not valid RFC 8259 JSON."""
    raise ValueError(f"non-standard numeric constant {value}")


def find_non_finite_number(value: Any, path: str = "$") -> Optional[str]:
    """Return the JSON path of the first non-finite parsed float, if any."""
    if isinstance(value, float) and not math.isfinite(value):
        return path
    if isinstance(value, dict):
        for key, child in value.items():
            found = find_non_finite_number(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = find_non_finite_number(child, f"{path}[{index}]")
            if found:
                return found
    return None


def is_finite_derived_number(value: Any) -> bool:
    """Return whether an aggregate statistic is safe to serialize as JSON."""
    if isinstance(value, int) and not isinstance(value, bool):
        return True
    return isinstance(value, float) and math.isfinite(value)


def aggregate_seeds(
    entries: List[Dict[str, Any]],
    warnings: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Aggregate unique seeded entries within one experiment configuration.

    Duplicate seed identities are ambiguous evidence. They are retained in
    the raw entries for diagnosis, but the whole affected aggregate group is
    suppressed and a provenance warning is emitted.
    """
    if warnings is None:
        warnings = []

    groups: Dict[Tuple, List[Dict[str, Any]]] = {}
    seen: Dict[Tuple, Dict[str, Any]] = {}
    duplicate_groups = set()
    for entry in entries:
        seed = entry.get("seed")
        if not isinstance(seed, int) or isinstance(seed, bool):
            continue
        key = (
            entry["round"],
            entry["experiment_id"],
            entry["config_fingerprint"],
            entry["evidence_contract_id"],
            entry["evidence_contract_fingerprint"],
            entry["outcome_id"],
            entry["analysis_protocol_id"],
            entry.get("method"),
            entry.get("group"),
        )
        identity = key + (seed,)
        if identity in seen:
            duplicate_groups.add(key)
            warnings.append(
                "Duplicate seeded result identity "
                f"(round={entry['round']}, "
                f"experiment_id={entry['experiment_id']!r}, "
                f"config_fingerprint={entry['config_fingerprint']!r}, "
                f"evidence_contract_id={entry['evidence_contract_id']!r}, "
                f"outcome_id={entry['outcome_id']!r}, "
                f"analysis_protocol_id={entry['analysis_protocol_id']!r}, "
                f"method={entry.get('method')!r}, group={entry.get('group')!r}, "
                f"seed={seed}) in {seen[identity]['file']} and {entry['file']}; "
                "aggregate suppressed"
            )
        else:
            seen[identity] = entry
        groups.setdefault(key, []).append(entry)

    aggregates: List[Dict[str, Any]] = []
    for (
        rnd,
        experiment_id,
        config_fingerprint,
        evidence_contract_id,
        evidence_contract_fingerprint,
        outcome_id,
        analysis_protocol_id,
        method,
        group,
    ), items in sorted(
        groups.items(),
        key=lambda item: (
            item[0][0],
            item[0][1],
            item[0][2],
            item[0][3],
            item[0][4],
            item[0][5],
            item[0][6],
            str(item[0][7]),
            str(item[0][8]),
        ),
    ):
        group_key = (
            rnd,
            experiment_id,
            config_fingerprint,
            evidence_contract_id,
            evidence_contract_fingerprint,
            outcome_id,
            analysis_protocol_id,
            method,
            group,
        )
        if group_key in duplicate_groups:
            continue
        seeds = sorted({e["seed"] for e in items})
        if len(seeds) < 2:
            continue

        metric_observations: Dict[str, List[Tuple[int, float, str]]] = {}
        for e in items:
            for k, v in e["metrics"].items():
                metric_observations.setdefault(k, []).append(
                    (e["seed"], v, e["file"])
                )

        metrics: Dict[str, Dict[str, Any]] = {}
        for k, observations in sorted(metric_observations.items()):
            metric_seeds = sorted({seed for seed, _, _ in observations})
            if len(metric_seeds) < 2:
                warnings.append(
                    f"Metric {k!r} for experiment_id={experiment_id!r}, "
                    f"config_fingerprint={config_fingerprint!r}, "
                    f"method={method!r}, group={group!r} has fewer than two "
                    f"seeds ({metric_seeds}); metric omitted"
                )
                continue

            vals = [value for _, value, _ in observations]
            try:
                mean = statistics.mean(vals)
                std = statistics.stdev(vals)
            except (OverflowError, ValueError, statistics.StatisticsError) as error:
                warnings.append(
                    f"Aggregate overflow or invalid derived statistic for metric "
                    f"{k!r}, experiment_id={experiment_id!r}, "
                    f"config_fingerprint={config_fingerprint!r}: {error}; "
                    "metric omitted"
                )
                continue

            if not is_finite_derived_number(mean) or not is_finite_derived_number(std):
                warnings.append(
                    f"Non-finite derived statistic for metric {k!r}, "
                    f"experiment_id={experiment_id!r}, "
                    f"config_fingerprint={config_fingerprint!r}; metric omitted"
                )
                continue

            metrics[k] = {
                "mean": mean,
                "std": std,
                "n": len(metric_seeds),
                "seeds": metric_seeds,
                "files": sorted({file for _, _, file in observations}),
            }

        if not metrics:
            continue

        aggregates.append({
            "round": rnd,
            "experiment_id": experiment_id,
            "config_fingerprint": config_fingerprint,
            "evidence_contract_id": evidence_contract_id,
            "evidence_contract_fingerprint": evidence_contract_fingerprint,
            "outcome_id": outcome_id,
            "analysis_protocol_id": analysis_protocol_id,
            "method": method,
            "group": group,
            "n_seeds": len(seeds),
            "seeds": seeds,
            "files": sorted({e["file"] for e in items}),
            "metrics": metrics,
        })
    return aggregates


def collect_results(
    results_dir: Path,
    metric_keys: Optional[List[str]] = None,
    excluded_paths: Optional[List[Path]] = None,
) -> Dict[str, Any]:
    """
    Collect all results from a directory into a structured format.

    Returns:
        {
            "results_dir": str,
            "files_scanned": int,       # candidates excluding configured outputs
            "files_with_metrics": int,   # distinct files that yielded entries
            "entries_extracted": int,    # total entry rows extracted
            "entries": [
                {
                    "file": str (relative path),
                    "round": positive int,
                    "seed": nonnegative int or "aggregate",
                    "experiment_id": str,
                    "config_fingerprint": str,
                    "evidence_contract_id": str,
                    "evidence_contract_fingerprint": str,
                    "outcome_id": str,
                    "analysis_protocol_id": str,
                    "meta": dict,
                    "metrics": {key: value},
                }
            ],
            "aggregates": [  # mean/std within one experiment/configuration
                {"round", "experiment_id", "config_fingerprint",
                 "evidence_contract_id", "evidence_contract_fingerprint",
                 "outcome_id", "analysis_protocol_id", "method", "group",
                 "n_seeds", "seeds", "files",
                 "metrics": {key: {"mean", "std", "n", "seeds", "files"}}}
            ],
            "warnings": [str]
        }
    """
    json_files = find_result_files(results_dir, excluded_paths)
    entries = []
    aggregation_entries = []
    warnings = []
    contract_identities: Dict[str, Dict[str, List[str]]] = {}

    def _filter_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
        if not metric_keys:
            return metrics
        filtered = {}
        for mk in metric_keys:
            for full_key, val in metrics.items():
                if mk in full_key:
                    filtered[full_key] = val
        return filtered

    for fpath in json_files:
        rel_path = str(fpath.relative_to(results_dir))
        try:
            is_file = fpath.is_file()
        except OSError as error:
            warnings.append(f"Cannot inspect {rel_path}: {error}")
            continue
        if not is_file:
            warnings.append(f"Cannot read {rel_path}: JSON candidate is not a file")
            continue

        try:
            raw_data = fpath.read_text(encoding="utf-8")
            data = json.loads(
                raw_data,
                parse_constant=reject_json_constant,
            )
        except (json.JSONDecodeError, UnicodeDecodeError, OSError, ValueError) as e:
            warnings.append(f"Cannot parse {rel_path}: {e}")
            continue

        non_finite_path = find_non_finite_number(data)
        if non_finite_path:
            warnings.append(
                f"Skipped {rel_path}: non-finite number at {non_finite_path}"
            )
            continue

        if not isinstance(data, dict):
            warnings.append(
                f"Skipped {rel_path}: top-level JSON value must be an object"
            )
            continue

        # Never re-ingest this script's own output, even if renamed
        if is_own_output(data):
            warnings.append(
                f"Skipped {rel_path}: looks like collect_results.py output, "
                f"not an experiment result"
            )
            continue

        meta, meta_warnings = extract_meta(data)
        for mw in meta_warnings:
            warnings.append(f"{rel_path}: {mw}")
        if meta_warnings:
            continue

        rnd = meta["round"]
        seed = meta["seed"]
        experiment_id = meta["experiment_id"]
        config_fingerprint = meta["config_fingerprint"]
        evidence_contract_id = meta["evidence_contract_id"]
        evidence_contract_fingerprint = meta["evidence_contract_fingerprint"]
        outcome_id = meta["outcome_id"]
        analysis_protocol_id = meta["analysis_protocol_id"]
        contract_identities.setdefault(evidence_contract_id, {}).setdefault(
            evidence_contract_fingerprint, []
        ).append(rel_path)

        # Mode 1: Extract per-method rows from arrays
        method_rows = extract_method_rows(data)
        top_metrics = extract_metrics_flat(data)
        if not method_rows and not top_metrics:
            warnings.append(
                f"Skipped {rel_path}: no finite numeric metrics were found"
            )
            continue

        if method_rows:
            for row in method_rows:
                unfiltered_entry = {
                    "file": rel_path,
                    "round": rnd,
                    "seed": seed,
                    "experiment_id": experiment_id,
                    "config_fingerprint": config_fingerprint,
                    "evidence_contract_id": evidence_contract_id,
                    "evidence_contract_fingerprint": evidence_contract_fingerprint,
                    "outcome_id": outcome_id,
                    "analysis_protocol_id": analysis_protocol_id,
                    "method": row["method"],
                    "group": row["group"],
                    "meta": meta,
                    "metrics": row["metrics"],
                }
                aggregation_entries.append(unfiltered_entry)
                metrics = _filter_metrics(row["metrics"])
                if metrics:
                    entries.append({**unfiltered_entry, "metrics": metrics})

        # Mode 2: Extract top-level scalar metrics
        if top_metrics:
            top_entry = {
                "file": rel_path,
                "round": rnd,
                "seed": seed,
                "experiment_id": experiment_id,
                "config_fingerprint": config_fingerprint,
                "evidence_contract_id": evidence_contract_id,
                "evidence_contract_fingerprint": evidence_contract_fingerprint,
                "outcome_id": outcome_id,
                "analysis_protocol_id": analysis_protocol_id,
                "method": None,
                "group": None,
                "meta": meta,
                "metrics": top_metrics,
            }
            aggregation_entries.append(top_entry)
            filtered_top_metrics = _filter_metrics(top_metrics)
            if filtered_top_metrics:
                entries.append({**top_entry, "metrics": filtered_top_metrics})

    for contract_id, fingerprints in sorted(contract_identities.items()):
        if len(fingerprints) > 1:
            sources = "; ".join(
                f"{fingerprint}: {', '.join(sorted(paths))}"
                for fingerprint, paths in sorted(fingerprints.items())
            )
            warnings.append(
                "Evidence Contract ID reused with multiple fingerprints "
                f"({contract_id!r}); create a new versioned ID instead. {sources}"
            )

    aggregates = aggregate_seeds(aggregation_entries, warnings)
    if metric_keys:
        filtered_aggregates = []
        for aggregate in aggregates:
            metrics = _filter_metrics(aggregate["metrics"])
            if metrics:
                filtered_aggregates.append({**aggregate, "metrics": metrics})
        aggregates = filtered_aggregates
    return {
        "results_dir": str(results_dir),
        "files_scanned": len(json_files),
        "files_with_metrics": len({e["file"] for e in entries}),
        "entries_extracted": len(entries),
        "entries": entries,
        "aggregates": aggregates,
        "warnings": warnings,
    }


def group_by_round(entries: List[Dict]) -> Dict[Optional[int], List[Dict]]:
    """Group entries by round number."""
    groups: Dict[Optional[int], List[Dict]] = {}
    for entry in entries:
        rnd = entry["round"]
        groups.setdefault(rnd, []).append(entry)
    return dict(sorted(groups.items(), key=lambda x: (x[0] is None, x[0] or 0)))


_METHOD_COL_WIDTH = 35
_FILE_COL_WIDTH = 40


def _short_key(k: str) -> str:
    """Strip dotted prefix from metric key for column headers."""
    return k.split(".")[-1] if "." in k else k


def format_markdown(collected: Dict[str, Any]) -> str:
    """Format collected results as a Markdown comparison table."""
    lines = []
    lines.append("# Experiment Results Comparison")
    lines.append("")
    lines.append(f"Source: `{collected['results_dir']}`")
    lines.append(f"Files scanned: {collected['files_scanned']}, "
                 f"with metrics: {collected['files_with_metrics']}, "
                 f"entries extracted: {collected['entries_extracted']}")
    lines.append("")

    if collected["warnings"]:
        lines.append("## Warnings")
        for w in collected["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    entries = collected["entries"]
    if not entries:
        lines.append("No result files with extractable metrics found.")
        return "\n".join(lines)

    # Collect all unique metric keys across all entries
    all_keys = set()
    for entry in entries:
        all_keys.update(entry["metrics"].keys())
    sorted_keys = sorted(all_keys)

    # Group by round
    groups = group_by_round(entries)

    for rnd, group_entries in groups.items():
        rnd_label = f"Round {rnd}" if rnd is not None else "Unassigned"
        lines.append(f"## {rnd_label}")
        lines.append("")

        # Separate method-rows from file-level rows
        method_entries = [e for e in group_entries if e.get("method")]
        file_entries = [e for e in group_entries if not e.get("method")]

        # Render method comparison tables (grouped by source file)
        if method_entries:
            by_file: Dict[str, List[Dict]] = {}
            for e in method_entries:
                by_file.setdefault(e["file"], []).append(e)

            for fname, rows in by_file.items():
                lines.append(f"**{fname}**")
                lines.append("")

                # Collect metric keys for this table
                mk = set()
                for r in rows:
                    mk.update(r["metrics"].keys())
                mk_sorted = sorted(mk)
                short_keys = [_short_key(k) for k in mk_sorted]

                header = "| Method | " + " | ".join(short_keys) + " |"
                sep = "|--------|" + "|".join(["------"] * len(short_keys)) + "|"
                lines.append(header)
                lines.append(sep)

                for r in rows:
                    method = r["method"]
                    if len(method) > _METHOD_COL_WIDTH:
                        method = method[:_METHOD_COL_WIDTH - 3] + "..."
                    vals = []
                    for k in mk_sorted:
                        v = r["metrics"].get(k)
                        if v is not None:
                            vals.append(f"{v:.4f}" if isinstance(v, float) else str(v))
                        else:
                            vals.append("-")
                    lines.append(f"| {method} | " + " | ".join(vals) + " |")

                lines.append("")

        # Render file-level metrics
        if file_entries:
            fk = set()
            for e in file_entries:
                fk.update(e["metrics"].keys())
            fk_sorted = [k for k in sorted_keys if k in fk]
            short_keys = [_short_key(k) for k in fk_sorted]

            if fk_sorted:
                header = "| File | " + " | ".join(short_keys) + " |"
                sep = "|------|" + "|".join(["------"] * len(short_keys)) + "|"
                lines.append(header)
                lines.append(sep)

                for entry in file_entries:
                    fname = entry["file"]
                    if len(fname) > _FILE_COL_WIDTH:
                        fname = "..." + fname[-(_FILE_COL_WIDTH - 3):]
                    vals = []
                    for k in fk_sorted:
                        v = entry["metrics"].get(k)
                        if v is not None:
                            vals.append(f"{v:.4f}" if isinstance(v, float) else str(v))
                        else:
                            vals.append("-")
                    lines.append(f"| {fname} | " + " | ".join(vals) + " |")

                lines.append("")

    # Seed aggregates (mean +/- std across seeds)
    aggregates = collected.get("aggregates", [])
    if aggregates:
        lines.append("## Seed Aggregates (mean ± std across seeds)")
        lines.append("")
        for agg in aggregates:
            rnd_label = f"Round {agg['round']}"
            method_label = agg["method"] or "(file-level)"
            mk_sorted = sorted(agg["metrics"].keys())
            short_keys = [_short_key(k) for k in mk_sorted]

            lines.append(
                f"**{rnd_label} — {agg['experiment_id']} — {method_label}** "
                f"(config={agg['config_fingerprint']}, "
                f"contract={agg['evidence_contract_id']}, "
                f"outcome={agg['outcome_id']}, "
                f"analysis={agg['analysis_protocol_id']}, "
                f"n_seeds={agg['n_seeds']}, seeds={agg['seeds']})"
            )
            lines.append("")
            lines.append("| Metric | mean | std | n | seeds | sources |")
            lines.append("|--------|------|-----|---|-------|---------|")
            for k, sk in zip(mk_sorted, short_keys):
                stats = agg["metrics"][k]
                lines.append(
                    f"| {sk} | {stats['mean']:.4f} | {stats['std']:.4f} "
                    f"| {stats['n']} | {stats['seeds']} | "
                    f"{', '.join(stats['files'])} |"
                )
            lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect experiment results into structured comparison tables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s experiment/results/
  %(prog)s experiment/results/ --output-md comparison.md --output-json comparison.json
  %(prog)s experiment/results/ --metric-keys cls_auc,recon_ssim

Output:
  Prints a Markdown summary to stdout.
  With --output-md/--output-json, writes to files.
  JSON output includes source file paths for every metric (provenance).
""",
    )

    parser.add_argument(
        "results_dir",
        type=str,
        help="Directory containing experiment result JSON files",
    )
    parser.add_argument(
        "--output-md",
        type=str,
        default=None,
        help="Write Markdown comparison table to this file",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Write structured JSON (with provenance) to this file",
    )
    parser.add_argument(
        "--metric-keys",
        type=str,
        default=None,
        help="Comma-separated metric keys to include (partial match supported)",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        help="Exit with a nonzero status if any warnings were produced "
             "(makes the Phase 6 gate enforceable)",
    )

    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"ERROR: Not a directory: {results_dir}", file=sys.stderr)
        sys.exit(1)

    metric_keys = None
    if args.metric_keys:
        metric_keys = [k.strip() for k in args.metric_keys.split(",")]

    excluded_paths = [Path(args.output_json)] if args.output_json else None
    collected = collect_results(results_dir, metric_keys, excluded_paths)

    # Markdown output
    md_text = format_markdown(collected)
    print(md_text)

    if args.output_md:
        Path(args.output_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_md).write_text(md_text + "\n", encoding="utf-8")
        print(f"\nMarkdown saved to: {args.output_md}", file=sys.stderr)

    if args.output_json:
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(
            json.dumps(
                collected,
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )
        print(f"JSON saved to: {args.output_json}", file=sys.stderr)

    if args.fail_on_warnings and collected["warnings"]:
        print(f"\nERROR: {len(collected['warnings'])} warning(s) with "
              f"--fail-on-warnings set", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
