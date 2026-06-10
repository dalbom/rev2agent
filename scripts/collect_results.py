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
import fnmatch
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Top-level keys that identify this script's own output (comparison table).
# Such files must never be re-ingested as experiment results.
_OUTPUT_SIGNATURE_KEYS = {"results_dir", "files_scanned", "entries"}


def is_own_output(data: Any) -> bool:
    """Return True if parsed JSON looks like this script's own output."""
    return (
        isinstance(data, dict)
        and "_meta" not in data
        and _OUTPUT_SIGNATURE_KEYS <= set(data.keys())
    )


def find_result_files(results_dir: Path) -> List[Path]:
    """
    Find all non-empty JSON files under results_dir.

    Skips this script's own output (comparison_table*.json) so re-runs do
    not re-ingest the generated table, and tolerates broken symlinks.
    """
    json_files = sorted(results_dir.rglob("*.json"))
    found = []
    for f in json_files:
        if fnmatch.fnmatch(f.name, "comparison_table*.json"):
            continue
        try:
            if f.stat().st_size > 0:
                found.append(f)
        except OSError:
            continue  # broken symlink or vanished file
    return found


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
        if isinstance(val, (int, float)) and not isinstance(val, bool):
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
    Extract the _meta field. Returns (meta, warnings).

    The Phase 5 result file convention makes _meta mandatory: a missing
    _meta is inferred from top-level fields but reported as a warning,
    and a malformed (non-dict) _meta degrades to a warning instead of
    crashing the whole run.
    """
    warnings: List[str] = []
    if "_meta" in data:
        meta = data["_meta"]
        if isinstance(meta, dict):
            return meta, warnings
        warnings.append(
            f"_meta is not a dict (got {type(meta).__name__}); ignoring it"
        )
        return {}, warnings

    warnings.append("missing _meta (mandatory per Phase 5 convention); "
                    "inferring from top-level fields")
    meta = {}
    if "timestamp" in data:
        meta["timestamp"] = data["timestamp"]
    if "round" in data:
        meta["round"] = data["round"]
    return meta, warnings


_ROUND_RE = re.compile(r"(?:^|[_\-/])round(\d+)")
_SEED_RE = re.compile(r"(?:^|[_\-/])seed[_\-]?(\d+)", re.IGNORECASE)


def infer_round_from_path(path: Path) -> Optional[int]:
    """Try to infer round number from file path (e.g., round5_combined.json -> 5).

    The 'round' token must start a path component or follow a separator,
    so e.g. 'playground2' is not misread as round 2.
    """
    for part in [path.stem] + [p for p in path.parts]:
        m = _ROUND_RE.search(part)
        if m:
            return int(m.group(1))
    return None


def infer_seed(meta: Dict[str, Any], path_str: str) -> Optional[int]:
    """Infer the random seed from _meta or from the file name."""
    seed = meta.get("seed")
    if isinstance(seed, int) and not isinstance(seed, bool):
        return seed
    m = _SEED_RE.search(Path(path_str).stem)
    if m:
        return int(m.group(1))
    return None


def aggregate_seeds(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Group seeded entries by (round, method, group) and compute mean/std
    per metric across seeds. Only groups with >= 2 distinct seeds are
    aggregated (a single seed has no spread to report).
    """
    groups: Dict[Tuple, List[Dict[str, Any]]] = {}
    for entry in entries:
        if entry.get("seed") is None:
            continue
        key = (entry["round"], entry.get("method"), entry.get("group"))
        groups.setdefault(key, []).append(entry)

    aggregates: List[Dict[str, Any]] = []
    for (rnd, method, group), items in sorted(
        groups.items(),
        key=lambda x: (x[0][0] is None, x[0][0] or 0, str(x[0][1]), str(x[0][2])),
    ):
        seeds = sorted({e["seed"] for e in items})
        if len(seeds) < 2:
            continue

        metric_vals: Dict[str, List[float]] = {}
        for e in items:
            for k, v in e["metrics"].items():
                metric_vals.setdefault(k, []).append(v)

        metrics: Dict[str, Dict[str, Any]] = {}
        for k, vals in sorted(metric_vals.items()):
            metrics[k] = {
                "mean": sum(vals) / len(vals),
                "std": statistics.stdev(vals) if len(vals) > 1 else 0.0,
                "n": len(vals),
            }

        aggregates.append({
            "round": rnd,
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
) -> Dict[str, Any]:
    """
    Collect all results from a directory into a structured format.

    Returns:
        {
            "results_dir": str,
            "files_scanned": int,
            "files_with_metrics": int,   # distinct files that yielded entries
            "entries_extracted": int,    # total entry rows extracted
            "entries": [
                {
                    "file": str (relative path),
                    "round": int or null,
                    "seed": int or null,
                    "meta": dict,
                    "metrics": {key: value},
                }
            ],
            "aggregates": [  # mean/std across seeds per (round, method, group)
                {"round", "method", "group", "n_seeds", "seeds", "files",
                 "metrics": {key: {"mean", "std", "n"}}}
            ],
            "warnings": [str]
        }
    """
    json_files = find_result_files(results_dir)
    entries = []
    warnings = []

    def _filter_metrics(metrics: Dict[str, float]) -> Dict[str, float]:
        if not metric_keys:
            return metrics
        filtered = {}
        for mk in metric_keys:
            for full_key, val in metrics.items():
                if mk in full_key:
                    filtered[full_key] = val
        return filtered

    for fpath in json_files:
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            warnings.append(f"Cannot parse {fpath.name}: {e}")
            continue

        if not isinstance(data, dict):
            continue

        rel_path = str(fpath.relative_to(results_dir))

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
        rnd = meta.get("round") or infer_round_from_path(fpath)
        seed = infer_seed(meta, rel_path)

        # Mode 1: Extract per-method rows from arrays
        method_rows = extract_method_rows(data)
        if method_rows:
            for row in method_rows:
                metrics = _filter_metrics(row["metrics"])
                if metrics:
                    entries.append({
                        "file": rel_path,
                        "round": rnd,
                        "seed": seed,
                        "method": row["method"],
                        "group": row["group"],
                        "meta": meta,
                        "metrics": metrics,
                    })

        # Mode 2: Extract top-level scalar metrics
        top_metrics = extract_metrics_flat(data)
        top_metrics = _filter_metrics(top_metrics)
        if top_metrics:
            entries.append({
                "file": rel_path,
                "round": rnd,
                "seed": seed,
                "method": None,
                "group": None,
                "meta": meta,
                "metrics": top_metrics,
            })

    return {
        "results_dir": str(results_dir),
        "files_scanned": len(json_files),
        "files_with_metrics": len({e["file"] for e in entries}),
        "entries_extracted": len(entries),
        "entries": entries,
        "aggregates": aggregate_seeds(entries),
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
            rnd_label = f"Round {agg['round']}" if agg["round"] is not None else "Unassigned"
            method_label = agg["method"] or "(file-level)"
            mk_sorted = sorted(agg["metrics"].keys())
            short_keys = [_short_key(k) for k in mk_sorted]

            lines.append(f"**{rnd_label} — {method_label}** "
                         f"(n_seeds={agg['n_seeds']}, seeds={agg['seeds']})")
            lines.append("")
            lines.append("| Metric | mean | std | n |")
            lines.append("|--------|------|-----|---|")
            for k, sk in zip(mk_sorted, short_keys):
                stats = agg["metrics"][k]
                lines.append(
                    f"| {sk} | {stats['mean']:.4f} | {stats['std']:.4f} "
                    f"| {stats['n']} |"
                )
            lines.append("")
            lines.append(f"Sources: {', '.join(agg['files'])}")
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

    collected = collect_results(results_dir, metric_keys)

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
            json.dumps(collected, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"JSON saved to: {args.output_json}", file=sys.stderr)

    if args.fail_on_warnings and collected["warnings"]:
        print(f"\nERROR: {len(collected['warnings'])} warning(s) with "
              f"--fail-on-warnings set", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
