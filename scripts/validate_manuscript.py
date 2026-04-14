#!/usr/bin/env python3
"""
Automated validation checks for a LaTeX manuscript.

Checks citation integrity, cross-reference integrity, required sections,
placeholder/TODO detection, figure file existence, and basic consistency.

Usage:
    python validate_manuscript.py --manuscript-dir path/to/manuscript/ \
        [--bib references.bib] [--strict] [--output report.txt]

Exit codes:
    0 - No errors (warnings are OK)
    1 - One or more errors found
    2 - Strict mode and one or more warnings found (even if no errors)
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Issue(NamedTuple):
    level: str          # "ERROR" or "WARNING"
    code: str           # e.g. "E001", "W003"
    message: str


# Counters used to assign sequential codes
_error_counter = 0
_warning_counter = 0


def _make_error(message: str) -> Issue:
    global _error_counter
    _error_counter += 1
    return Issue("ERROR", f"E{_error_counter:03d}", message)


def _make_warning(message: str) -> Issue:
    global _warning_counter
    _warning_counter += 1
    return Issue("WARNING", f"W{_warning_counter:03d}", message)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def collect_tex_files(manuscript_dir: Path) -> List[Path]:
    """Recursively find all .tex files under the manuscript directory."""
    tex_files = sorted(manuscript_dir.rglob("*.tex"))
    return tex_files


def read_file_lines(path: Path) -> List[str]:
    """Read a file and return its lines (empty list on failure)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except OSError:
        return []


def strip_comments(line: str) -> str:
    """Remove LaTeX line comments (% ...) but not escaped \\%."""
    # Walk the string: remove everything after an unescaped %
    result = []
    i = 0
    while i < len(line):
        if line[i] == '%' and (i == 0 or line[i - 1] != '\\'):
            break
        result.append(line[i])
        i += 1
    return ''.join(result)


def relative_display(path: Path, base: Path) -> str:
    """Return a display-friendly relative path string."""
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# 1. Citation integrity
# ---------------------------------------------------------------------------

# Matches \cite{...}, \citep{...}, \citet{...}, \citeauthor{...},
# \citeyear{...}, \citealt{...}, \citealp{...}, \Citet{...}, etc.
_CITE_RE = re.compile(
    r'\\(?:[Cc]ite[a-zA-Z]*)\s*'       # command name
    r'(?:\[[^\]]*\]\s*)*'                # optional [...] arguments (e.g. prenote, postnote)
    r'\{([^}]+)\}'                       # mandatory {keys}
)

_BIB_ENTRY_RE = re.compile(
    r'@\w+\s*\{\s*([^,\s]+)\s*,'        # @type{key,
)


def extract_citations(tex_files: List[Path], base: Path) -> Dict[str, List[Tuple[str, int]]]:
    """Return {cite_key: [(file_display, line_no), ...]}."""
    citations: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        display = relative_display(tex_path, base)
        for lineno, raw_line in enumerate(lines, start=1):
            line = strip_comments(raw_line)
            for m in _CITE_RE.finditer(line):
                keys_str = m.group(1)
                for key in keys_str.split(','):
                    key = key.strip()
                    if key:
                        citations[key].append((display, lineno))
    return citations


def parse_bib_keys(bib_path: Path) -> Set[str]:
    """Return the set of entry keys in a .bib file."""
    keys: Set[str] = set()
    lines = read_file_lines(bib_path)
    for line in lines:
        m = _BIB_ENTRY_RE.search(line)
        if m:
            keys.add(m.group(1).strip())
    return keys


def check_citations(tex_files: List[Path], bib_path: Path, base: Path) -> List[Issue]:
    issues: List[Issue] = []
    citations = extract_citations(tex_files, base)
    bib_keys = parse_bib_keys(bib_path) if bib_path.exists() else set()

    if not bib_path.exists():
        issues.append(_make_error(f"BibTeX file not found: {relative_display(bib_path, base)}"))
        return issues

    # Cited but not in bib
    for key, locations in sorted(citations.items()):
        if key not in bib_keys:
            loc_str = "; ".join(f"{f}:{ln}" for f, ln in locations)
            issues.append(
                _make_error(f"Citation '{key}' used in {loc_str} but not in {relative_display(bib_path, base)}")
            )

    # In bib but not cited
    cited_keys = set(citations.keys())
    for key in sorted(bib_keys - cited_keys):
        issues.append(
            _make_warning(f"BibTeX entry '{key}' not cited in any .tex file")
        )

    return issues


# ---------------------------------------------------------------------------
# 2. Cross-reference integrity
# ---------------------------------------------------------------------------

_LABEL_RE = re.compile(r'\\label\{([^}]+)\}')

# \ref, \eqref, \autoref, \cref, \Cref, \pageref, \nameref, \hyperref[label]
_REF_RE = re.compile(
    r'\\(?:eq)?ref\{([^}]+)\}'
    r'|\\(?:auto|c|C|page|name)ref\{([^}]+)\}'
    r'|\\hyperref\[([^\]]+)\]'
)


def extract_labels(tex_files: List[Path], base: Path) -> Dict[str, Tuple[str, int]]:
    """Return {label: (file_display, line_no)}."""
    labels: Dict[str, Tuple[str, int]] = {}
    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        display = relative_display(tex_path, base)
        for lineno, raw_line in enumerate(lines, start=1):
            line = strip_comments(raw_line)
            for m in _LABEL_RE.finditer(line):
                lbl = m.group(1).strip()
                if lbl not in labels:
                    labels[lbl] = (display, lineno)
    return labels


def extract_refs(tex_files: List[Path], base: Path) -> Dict[str, List[Tuple[str, int]]]:
    """Return {label: [(file_display, line_no), ...]}."""
    refs: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        display = relative_display(tex_path, base)
        for lineno, raw_line in enumerate(lines, start=1):
            line = strip_comments(raw_line)
            for m in _REF_RE.finditer(line):
                # The regex has three capture groups; exactly one will be non-None
                lbl = m.group(1) or m.group(2) or m.group(3)
                if lbl:
                    refs[lbl.strip()].append((display, lineno))
    return refs


def check_cross_references(tex_files: List[Path], base: Path) -> List[Issue]:
    issues: List[Issue] = []
    labels = extract_labels(tex_files, base)
    refs = extract_refs(tex_files, base)

    # Referenced but not defined
    for lbl, locations in sorted(refs.items()):
        if lbl not in labels:
            loc_str = "; ".join(f"{f}:{ln}" for f, ln in locations)
            issues.append(
                _make_error(f"Reference '\\ref{{{lbl}}}' used in {loc_str} but label never defined")
            )

    # Defined but not referenced
    referenced_labels = set(refs.keys())
    for lbl in sorted(set(labels.keys()) - referenced_labels):
        f, ln = labels[lbl]
        issues.append(
            _make_warning(f"Label '{lbl}' defined in {f}:{ln} but never referenced")
        )

    return issues


# ---------------------------------------------------------------------------
# 3. Required sections check
# ---------------------------------------------------------------------------

DEFAULT_REQUIRED_SECTIONS = [
    "abstract",
    "introduction",
    "related work",
    "method",
    "experiments",
    "conclusion",
]

# Matches \section{...}, \section*{...}, and also common variants
_SECTION_RE = re.compile(r'\\section\*?\{([^}]+)\}', re.IGNORECASE)
_ABSTRACT_BEGIN_RE = re.compile(r'\\begin\{abstract\}')


def check_required_sections(
    tex_files: List[Path],
    required: Optional[List[str]] = None,
) -> List[Issue]:
    issues: List[Issue] = []
    if required is None:
        required = DEFAULT_REQUIRED_SECTIONS

    # Collect all section titles (lowered) and whether abstract environment exists
    found_sections: Set[str] = set()
    has_abstract_env = False

    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        for raw_line in lines:
            line = strip_comments(raw_line)
            for m in _SECTION_RE.finditer(line):
                found_sections.add(m.group(1).strip().lower())
            if _ABSTRACT_BEGIN_RE.search(line):
                has_abstract_env = True

    for req in required:
        req_lower = req.lower()
        if req_lower == "abstract":
            # Accept either \section{Abstract} or \begin{abstract}
            if not has_abstract_env and "abstract" not in found_sections:
                issues.append(_make_warning(f"Required section missing: '{req}'"))
        else:
            # Fuzzy check: the required name should be a substring of some section title
            # e.g. "method" matches "Method", "Methodology", "Our Method", etc.
            if not any(req_lower in s for s in found_sections):
                issues.append(_make_warning(f"Required section missing: '{req}'"))

    return issues


# ---------------------------------------------------------------------------
# 4. Placeholder / TODO detection
# ---------------------------------------------------------------------------

_PLACEHOLDER_PATTERNS = [
    # Pattern, description
    (re.compile(r'\bTODO\b', re.IGNORECASE), "TODO"),
    (re.compile(r'\bFIXME\b', re.IGNORECASE), "FIXME"),
    (re.compile(r'\bXXX\b'), "XXX"),
    (re.compile(r'\bTBD\b'), "TBD"),
    (re.compile(r'\bPLACEHOLDER\b', re.IGNORECASE), "PLACEHOLDER"),
    (re.compile(r'\[\?\]'), "[?]"),
    (re.compile(r'\?\?'), "??"),
    (re.compile(r'\bINSERT\b'), "INSERT"),
    (re.compile(r'\bFILL\s+IN\b', re.IGNORECASE), "FILL IN"),
    (re.compile(r'\\textcolor\{red\}'), "\\textcolor{red}"),
    (re.compile(r'\\hl\{'), "\\hl{"),
]


def check_placeholders(tex_files: List[Path], base: Path) -> List[Issue]:
    issues: List[Issue] = []
    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        display = relative_display(tex_path, base)
        for lineno, raw_line in enumerate(lines, start=1):
            # Check both the raw line (catches % TODO comments) and the content
            for pat, desc in _PLACEHOLDER_PATTERNS:
                m = pat.search(raw_line)
                if m:
                    # Show a snippet of context around the match
                    snippet = raw_line.strip()
                    if len(snippet) > 100:
                        start = max(0, m.start() - 30)
                        snippet = snippet[start:start + 100] + "..."
                    issues.append(
                        _make_warning(f"{desc} found in {display}:{lineno}: \"{snippet}\"")
                    )
                    break  # one issue per line is enough
    return issues


# ---------------------------------------------------------------------------
# 5. Figure file existence
# ---------------------------------------------------------------------------

_INCLUDEGRAPHICS_RE = re.compile(
    r'\\includegraphics'
    r'(?:\s*\[[^\]]*\])*'        # optional [options]
    r'\s*\{([^}]+)\}'            # {path}
)


def check_figures(tex_files: List[Path], manuscript_dir: Path, base: Path) -> List[Issue]:
    issues: List[Issue] = []

    # Also check for \graphicspath{...}
    graphics_paths: List[Path] = [manuscript_dir]
    _graphicspath_re = re.compile(r'\\graphicspath\{([^}]+)\}')

    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        for raw_line in lines:
            line = strip_comments(raw_line)
            m = _graphicspath_re.search(line)
            if m:
                # \graphicspath{{dir1/}{dir2/}} — extract the inner braces
                inner = m.group(1)
                for dm in re.finditer(r'\{([^}]*)\}', inner):
                    p = Path(dm.group(1))
                    if not p.is_absolute():
                        p = manuscript_dir / p
                    graphics_paths.append(p)

    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        display = relative_display(tex_path, base)
        for lineno, raw_line in enumerate(lines, start=1):
            line = strip_comments(raw_line)
            for m in _INCLUDEGRAPHICS_RE.finditer(line):
                fig_path_str = m.group(1).strip()
                # Try resolving the figure file
                found = False
                # Common extensions to try if no extension given
                extensions_to_try = [""]
                if not os.path.splitext(fig_path_str)[1]:
                    extensions_to_try = ["", ".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg"]

                for search_dir in graphics_paths:
                    for ext in extensions_to_try:
                        candidate = search_dir / (fig_path_str + ext)
                        if candidate.exists():
                            found = True
                            break
                    if found:
                        break

                if not found:
                    issues.append(
                        _make_error(
                            f"Figure '{fig_path_str}' referenced in {display}:{lineno} "
                            f"but file not found"
                        )
                    )

    return issues


# ---------------------------------------------------------------------------
# 6. Basic consistency checks
# ---------------------------------------------------------------------------

_BEGIN_RE = re.compile(r'\\begin\{(\w+)\}')
_END_RE = re.compile(r'\\end\{(\w+)\}')

# Section-level commands, ordered by hierarchy depth
_SECTION_CMDS_RE = re.compile(
    r'\\(part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\{'
)


def check_environment_matching(tex_files: List[Path], base: Path) -> List[Issue]:
    """Check for unmatched \\begin{}/\\end{} pairs within each file."""
    issues: List[Issue] = []
    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        display = relative_display(tex_path, base)

        # Stack of (env_name, line_no)
        stack: List[Tuple[str, int]] = []

        for lineno, raw_line in enumerate(lines, start=1):
            line = strip_comments(raw_line)
            # Process all \begin and \end in order of appearance
            events: List[Tuple[int, str, str]] = []  # (position, 'begin'|'end', env_name)

            for m in _BEGIN_RE.finditer(line):
                events.append((m.start(), 'begin', m.group(1)))
            for m in _END_RE.finditer(line):
                events.append((m.start(), 'end', m.group(1)))

            events.sort(key=lambda x: x[0])

            for _, kind, env_name in events:
                if kind == 'begin':
                    stack.append((env_name, lineno))
                else:  # 'end'
                    if not stack:
                        issues.append(
                            _make_error(
                                f"Unmatched \\end{{{env_name}}} in {display}:{lineno} "
                                f"with no preceding \\begin{{{env_name}}}"
                            )
                        )
                    elif stack[-1][0] != env_name:
                        open_env, open_line = stack[-1]
                        issues.append(
                            _make_error(
                                f"Environment mismatch in {display}: \\begin{{{open_env}}} "
                                f"at line {open_line} closed by \\end{{{env_name}}} at line {lineno}"
                            )
                        )
                        stack.pop()
                    else:
                        stack.pop()

        # Anything left on the stack is unclosed
        for env_name, open_line in stack:
            issues.append(
                _make_error(
                    f"Unclosed \\begin{{{env_name}}} in {display}:{open_line} "
                    f"(no matching \\end{{{env_name}}})"
                )
            )

    return issues


def check_empty_sections(tex_files: List[Path], base: Path) -> List[Issue]:
    """Detect section headers immediately followed by another section header with no content."""
    issues: List[Issue] = []

    for tex_path in tex_files:
        lines = read_file_lines(tex_path)
        display = relative_display(tex_path, base)

        prev_section: Optional[Tuple[str, str, int]] = None  # (command, title, lineno)

        for lineno, raw_line in enumerate(lines, start=1):
            line = strip_comments(raw_line).strip()

            # Skip blank lines and comments for the purpose of detecting emptiness
            if not line:
                continue

            m = _SECTION_CMDS_RE.search(line)
            if m:
                # Extract the full title
                cmd = m.group(1)
                title_match = re.search(
                    r'\\' + re.escape(cmd) + r'\*?\{([^}]*)\}', line
                )
                title = title_match.group(1) if title_match else "?"

                if prev_section is not None:
                    prev_cmd, prev_title, prev_lineno = prev_section
                    # Only flag if the new section is at the same or higher level
                    # (i.e., not a subsection inside a section)
                    hierarchy = [
                        "part", "chapter", "section", "subsection",
                        "subsubsection", "paragraph", "subparagraph",
                    ]
                    prev_level = hierarchy.index(prev_cmd) if prev_cmd in hierarchy else 99
                    curr_level = hierarchy.index(cmd) if cmd in hierarchy else 99
                    if curr_level <= prev_level:
                        issues.append(
                            _make_warning(
                                f"Empty section '\\{prev_cmd}{{{prev_title}}}' in "
                                f"{display}:{prev_lineno} — followed immediately by "
                                f"'\\{cmd}{{{title}}}' at line {lineno} with no content"
                            )
                        )

                prev_section = (cmd, title, lineno)
            else:
                # Non-blank, non-section line — means the previous section has content
                prev_section = None

    return issues


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def format_report(issues: List[Issue]) -> str:
    errors = [i for i in issues if i.level == "ERROR"]
    warnings = [i for i in issues if i.level == "WARNING"]

    lines: List[str] = []
    lines.append("MANUSCRIPT VALIDATION REPORT")
    lines.append("=" * 28)
    lines.append(f"Errors:   {len(errors)}")
    lines.append(f"Warnings: {len(warnings)}")
    lines.append("")

    if errors:
        lines.append("ERRORS:")
        for issue in errors:
            lines.append(f"  [{issue.code}] {issue.message}")
        lines.append("")

    if warnings:
        lines.append("WARNINGS:")
        for issue in warnings:
            lines.append(f"  [{issue.code}] {issue.message}")
        lines.append("")

    if not errors and not warnings:
        lines.append("No issues found.")
        lines.append("")

    if errors:
        lines.append("RESULT: FAIL")
    else:
        lines.append("RESULT: PASS")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a LaTeX manuscript for common issues.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--manuscript-dir",
        required=True,
        type=Path,
        help="Path to the manuscript directory containing .tex files",
    )
    parser.add_argument(
        "--bib",
        default="references.bib",
        help="Name of the BibTeX file (relative to manuscript-dir, default: references.bib)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures (exit code 2 if any warnings)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report to this file (in addition to stdout)",
    )
    parser.add_argument(
        "--required-sections",
        nargs="*",
        default=None,
        help="Override default required sections list",
    )

    args = parser.parse_args()

    manuscript_dir = args.manuscript_dir.resolve()
    if not manuscript_dir.is_dir():
        print(f"Error: manuscript directory not found: {manuscript_dir}", file=sys.stderr)
        return 1

    bib_path = manuscript_dir / args.bib

    # Collect all .tex files
    tex_files = collect_tex_files(manuscript_dir)
    if not tex_files:
        print(f"Error: no .tex files found in {manuscript_dir}", file=sys.stderr)
        return 1

    print(f"Validating manuscript in: {manuscript_dir}")
    print(f"Found {len(tex_files)} .tex file(s)")
    print(f"BibTeX file: {bib_path}")
    print()

    # Reset issue counters
    global _error_counter, _warning_counter
    _error_counter = 0
    _warning_counter = 0

    # Run all checks
    all_issues: List[Issue] = []

    all_issues.extend(check_citations(tex_files, bib_path, manuscript_dir))
    all_issues.extend(check_cross_references(tex_files, manuscript_dir))
    all_issues.extend(check_required_sections(tex_files, args.required_sections))
    all_issues.extend(check_placeholders(tex_files, manuscript_dir))
    all_issues.extend(check_figures(tex_files, manuscript_dir, manuscript_dir))
    all_issues.extend(check_environment_matching(tex_files, manuscript_dir))
    all_issues.extend(check_empty_sections(tex_files, manuscript_dir))

    # Generate report
    report = format_report(all_issues)
    print(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
            f.write("\n")
        print(f"\nReport written to: {args.output}")

    # Determine exit code
    errors = [i for i in all_issues if i.level == "ERROR"]
    warnings = [i for i in all_issues if i.level == "WARNING"]

    if errors:
        return 1
    if args.strict and warnings:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
