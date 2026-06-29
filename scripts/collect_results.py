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

To avoid ingesting its own output on subsequent runs, the collector always
excludes files named "comparison_table.json" or "comparison.json" (legacy GUI
output name), as well as the files given via --output-json / --output-md.

Requires only Python 3.10+ stdlib (no external dependencies).
"""

import sys
import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Basenames of the collector's own outputs (current and legacy GUI name),
# always excluded from scanning so the collector never ingests its own output.
_ALWAYS_EXCLUDED_BASENAMES = {"comparison_table.json", "comparison.json"}


def find_result_files(
    results_dir: Path,
    exclude_paths: Optional[Set[Path]] = None,
) -> List[Path]:
    """
    Find all non-empty JSON files under results_dir.

    Skips any file whose resolved path is in exclude_paths (a set of
    RESOLVED Paths) or whose basename is in _ALWAYS_EXCLUDED_BASENAMES.
    """
    exclude_paths = exclude_paths or set()
    json_files = sorted(results_dir.rglob("*.json"))
    kept = []
    for f in json_files:
        if f.name in _ALWAYS_EXCLUDED_BASENAMES:
            continue
        if f.resolve() in exclude_paths:
            continue
        if f.stat().st_size > 0:
            kept.append(f)
    return kept


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


def extract_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract _meta field if present, otherwise infer from top-level fields."""
    if "_meta" in data:
        return data["_meta"]
    meta = {}
    if "timestamp" in data:
        meta["timestamp"] = data["timestamp"]
    if "round" in data:
        meta["round"] = data["round"]
    return meta


def infer_round_from_path(path: Path) -> Optional[int]:
    """Try to infer round number from file path (e.g., round5_combined.json -> 5)."""
    for part in [path.stem] + [p for p in path.parts]:
        m = re.search(r"round(\d+)", part)
        if m:
            return int(m.group(1))
    return None


def collect_results(
    results_dir: Path,
    metric_keys: Optional[List[str]] = None,
    exclude_paths: Optional[Set[Path]] = None,
) -> Dict[str, Any]:
    """
    Collect all results from a directory into a structured format.

    Returns:
        {
            "results_dir": str,
            "files_scanned": int,
            "files_with_metrics": int,
            "entries": [
                {
                    "file": str (relative path),
                    "round": int or null,
                    "meta": dict,
                    "metrics": {key: value},
                }
            ],
            "warnings": [str]
        }
    """
    json_files = find_result_files(results_dir, exclude_paths)
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

        meta = extract_meta(data)
        rnd = meta.get("round") or infer_round_from_path(fpath)
        rel_path = str(fpath.relative_to(results_dir))

        # Mode 1: Extract per-method rows from arrays
        method_rows = extract_method_rows(data)
        if method_rows:
            for row in method_rows:
                metrics = _filter_metrics(row["metrics"])
                if metrics:
                    entries.append({
                        "file": rel_path,
                        "round": rnd,
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
                "method": None,
                "group": None,
                "meta": meta,
                "metrics": top_metrics,
            })

    return {
        "results_dir": str(results_dir),
        "files_scanned": len(json_files),
        "files_with_metrics": len(entries),
        "entries": entries,
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


def _column_labels(keys: List[str]) -> List[str]:
    """
    Build column header labels for a table.

    Uses the short (prefix-stripped) form of each key when it is unique
    within the table; falls back to the full dotted key when the short
    form collides (e.g. keyword_rule.accuracy_mean vs majority.accuracy_mean).
    """
    shorts = [_short_key(k) for k in keys]
    counts: Dict[str, int] = {}
    for s in shorts:
        counts[s] = counts.get(s, 0) + 1
    return [s if counts[s] == 1 else k for k, s in zip(keys, shorts)]


def format_markdown(collected: Dict[str, Any]) -> str:
    """Format collected results as a Markdown comparison table."""
    lines = []
    lines.append("# Experiment Results Comparison")
    lines.append("")
    lines.append(f"Source: `{collected['results_dir']}`")
    lines.append(f"Files scanned: {collected['files_scanned']}, "
                 f"with metrics: {collected['files_with_metrics']}")
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
                short_keys = _column_labels(mk_sorted)

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
            short_keys = _column_labels(fk_sorted)

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

Exclusions:
  Files named comparison_table.json or comparison.json (legacy GUI output
  name) are ALWAYS excluded from scanning, as are the files passed via
  --output-json/--output-md, so the collector never ingests its own output.
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

    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"ERROR: Not a directory: {results_dir}", file=sys.stderr)
        sys.exit(1)

    metric_keys = None
    if args.metric_keys:
        metric_keys = [k.strip() for k in args.metric_keys.split(",")]

    exclude_paths: Set[Path] = set()
    if args.output_md:
        exclude_paths.add(Path(args.output_md).resolve())
    if args.output_json:
        exclude_paths.add(Path(args.output_json).resolve())

    collected = collect_results(results_dir, metric_keys, exclude_paths=exclude_paths)

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


if __name__ == "__main__":
    main()
