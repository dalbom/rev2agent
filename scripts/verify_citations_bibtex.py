#!/usr/bin/env python3
"""
BibTeX Citation Verification Script

Adapted from deep-research verify_citations.py for LaTeX manuscript projects.
Verifies BibTeX entries against DOI metadata, checks URL accessibility,
cross-references .tex citations with .bib entries, and detects common
LLM hallucination patterns in fabricated references.

Usage:
    python verify_citations_bibtex.py --bib references.bib --tex-dir sections/
    python verify_citations_bibtex.py --bib references.bib --tex-dir sections/ --strict
    python verify_citations_bibtex.py --bib references.bib --tex-dir sections/ --output report.txt

Requires only Python 3.10+ stdlib (no external dependencies).
"""

import sys
import argparse
import re
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib import request, error
from urllib.parse import quote


# ---------------------------------------------------------------------------
# BibTeX Parser (regex-based, handles standard entry types)
# ---------------------------------------------------------------------------

# Supported entry types
BIB_ENTRY_TYPES = {
    "article", "inproceedings", "book", "misc", "techreport",
    "incollection", "phdthesis", "mastersthesis", "proceedings",
    "inbook", "manual", "unpublished", "online",
}

# Regex to find the start of a BibTeX entry: @type{key,
_ENTRY_START_RE = re.compile(
    r"@(\w+)\s*\{\s*([^,\s]+)\s*,", re.IGNORECASE
)

# Regex to extract a field:  fieldname = {value}  or  fieldname = "value"  or  fieldname = number
_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{[^{}]*\})*)\}|\"([^\"]*)\"|(\d+))",
    re.DOTALL,
)


def parse_bibtex(text: str) -> Dict[str, Dict[str, str]]:
    """
    Parse BibTeX source text into a dict keyed by citation key.

    Each value is a dict with keys:
        _type   : entry type (article, inproceedings, ...)
        _key    : citation key
        title, author, year, doi, url, booktitle, journal, ... (as present)

    Field values have outer braces / quotes stripped but inner LaTeX is kept.
    """
    entries: Dict[str, Dict[str, str]] = {}

    # Split into potential entry blocks.  We find every @type{ and then
    # extract the balanced-brace body that follows.
    for m in _ENTRY_START_RE.finditer(text):
        entry_type = m.group(1).lower()
        key = m.group(2)

        if entry_type not in BIB_ENTRY_TYPES and entry_type != "string":
            continue
        if entry_type == "string":
            continue  # skip @string macros

        # Find the body: everything from after the opening '{' of @type{key,
        # to the matching closing '}'.
        start = m.end()
        depth = 1
        pos = start
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        body = text[start : pos - 1]

        # Extract fields from the body
        fields: Dict[str, str] = {"_type": entry_type, "_key": key}
        for fm in _FIELD_RE.finditer(body):
            fname = fm.group(1).lower()
            # value is in group 2 (braces), 3 (quotes), or 4 (bare number)
            fval = fm.group(2) if fm.group(2) is not None else (
                fm.group(3) if fm.group(3) is not None else fm.group(4)
            )
            if fval is not None:
                # Collapse internal whitespace
                fval = re.sub(r"\s+", " ", fval).strip()
                fields[fname] = fval

        entries[key] = fields

    return entries


# ---------------------------------------------------------------------------
# LaTeX Citation Scanner
# ---------------------------------------------------------------------------

# Matches \cite{...}, \citep{...}, \citet{...}, \citeauthor{...}, etc.
_CITE_RE = re.compile(r"\\cite\w*\{([^}]+)\}")


def scan_tex_citations(tex_dir: Path) -> Tuple[Set[str], Dict[str, List[str]]]:
    """
    Scan all .tex files under tex_dir (recursively) for \\cite commands.

    Returns:
        cited_keys : set of all citation keys referenced
        key_to_files: dict mapping each key to list of files where it appears
    """
    cited_keys: Set[str] = set()
    key_to_files: Dict[str, List[str]] = {}

    tex_files = sorted(tex_dir.rglob("*.tex"))
    if not tex_files:
        return cited_keys, key_to_files

    for tf in tex_files:
        try:
            content = tf.read_text(encoding="utf-8")
        except Exception:
            continue

        for m in _CITE_RE.finditer(content):
            # Handle multi-key citations: \cite{key1,key2,key3}
            raw_keys = m.group(1)
            for k in raw_keys.split(","):
                k = k.strip()
                if k:
                    cited_keys.add(k)
                    key_to_files.setdefault(k, []).append(str(tf.relative_to(tex_dir)))

    return cited_keys, key_to_files


# ---------------------------------------------------------------------------
# Verification Helpers
# ---------------------------------------------------------------------------

def verify_doi(doi: str) -> Tuple[bool, Dict]:
    """
    Resolve a DOI via https://doi.org/ with CSL-JSON content negotiation.

    Returns (success, metadata_dict).
    On success, metadata_dict contains title, year, authors, venue.
    On failure, metadata_dict contains an 'error' key.
    """
    try:
        url = f"https://doi.org/{quote(doi, safe='/')}"
        req = request.Request(url)
        req.add_header("Accept", "application/vnd.citationstyles.csl+json")
        req.add_header("User-Agent", "BibTeX-Citation-Verifier/1.0")

        with request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            issued = data.get("issued", {}).get("date-parts", [[None]])
            year = issued[0][0] if issued and issued[0] else None
            authors = [
                f"{a.get('family', '')} {a.get('given', '')}".strip()
                for a in data.get("author", [])
            ]
            return True, {
                "title": data.get("title", ""),
                "year": year,
                "authors": authors,
                "venue": data.get("container-title", ""),
            }
    except error.HTTPError as e:
        if e.code == 404:
            return False, {"error": "DOI not found (404)"}
        return False, {"error": f"HTTP {e.code}"}
    except error.URLError as e:
        return False, {"error": f"URL error: {e.reason}"}
    except Exception as e:
        return False, {"error": str(e)[:120]}


def verify_url(url: str) -> Tuple[bool, str]:
    """
    Check URL accessibility with a HEAD request.

    Returns (accessible, status_message).
    """
    try:
        req = request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0 (BibTeX Citation Verifier)")
        with request.urlopen(req, timeout=10) as resp:
            if resp.status < 400:
                return True, f"HTTP {resp.status} OK"
            return False, f"HTTP {resp.status}"
    except error.HTTPError as e:
        # Some servers reject HEAD but the resource exists; 403/405 are ambiguous
        if e.code in (403, 405):
            return True, f"HTTP {e.code} (HEAD rejected, resource likely exists)"
        return False, f"HTTP {e.code}"
    except error.URLError as e:
        return False, f"URL error: {e.reason}"
    except Exception as e:
        return False, f"Connection error: {str(e)[:80]}"


def title_similarity(t1: str, t2: str) -> float:
    """
    Jaccard similarity on lowercased word sets (punctuation stripped).
    Returns 0.0 -- 1.0.
    """
    def normalize(s: str) -> Set[str]:
        s = re.sub(r"[^\w\s]", " ", s.lower())
        return {w for w in s.split() if len(w) > 1}

    w1, w2 = normalize(t1), normalize(t2)
    if not w1 or not w2:
        return 0.0
    return len(w1 & w2) / len(w1 | w2)


# ---------------------------------------------------------------------------
# Hallucination Pattern Detector
# ---------------------------------------------------------------------------

# Suspicious title patterns (regex, human-readable description)
SUSPICIOUS_TITLE_PATTERNS = [
    (
        r"^(A |An |The )?(Study|Analysis|Review|Survey|Investigation) (of|on|into) ",
        "Generic academic title pattern",
    ),
    (
        r"^(Recent|Current|Modern|Contemporary) (Advances|Developments|Trends) in ",
        "Generic 'advances in' title pattern",
    ),
    (
        r": A (Comprehensive|Complete|Systematic|Thorough) (Review|Analysis|Guide|Overview)$",
        "Templated 'comprehensive review' suffix",
    ),
]

# Terms that should not appear in papers before year 2000
ANACHRONISTIC_TERMS = {
    "transformer", "transformers", "bert", "gpt", "llm", "llms",
    "diffusion model", "stable diffusion", "dall-e", "dalle",
    "generative adversarial", "gan", "deep learning", "neural radiance",
    "nerf", "clip",
}

# Current year ceiling for future-year check
CURRENT_YEAR = 2026


def detect_hallucination_patterns(entry: Dict[str, str]) -> List[str]:
    """
    Detect common LLM hallucination patterns in a BibTeX entry.
    Returns a list of human-readable issue strings.
    """
    issues: List[str] = []
    title = entry.get("title", "")
    year_str = entry.get("year", "")
    author = entry.get("author", "")

    # --- Missing critical fields ---
    if not title:
        issues.append("Missing title field")
    if not author:
        issues.append("Missing author field")
    if not year_str:
        issues.append("Missing year field")

    # --- Suspicious title patterns ---
    # Strip LaTeX commands for pattern matching
    clean_title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)
    clean_title = re.sub(r"[{}]", "", clean_title)

    for pattern, description in SUSPICIOUS_TITLE_PATTERNS:
        if re.search(pattern, clean_title, re.IGNORECASE):
            issues.append(f"Suspicious title pattern: {description}")

    # Placeholder text
    if any(x in clean_title.lower() for x in ("tbd", "todo", "placeholder", "example title")):
        issues.append("Placeholder text detected in title")

    # Very generic short title
    generic_words = {"overview", "introduction", "guide", "handbook", "manual", "tutorial"}
    if any(w in clean_title.lower() for w in generic_words) and len(clean_title.split()) < 5:
        issues.append("Very generic short title")

    # --- Year-based checks ---
    if year_str:
        try:
            year = int(year_str)
        except ValueError:
            issues.append(f"Non-numeric year: '{year_str}'")
            year = None

        if year is not None:
            if year > CURRENT_YEAR:
                issues.append(f"Future year: {year} (current year is {CURRENT_YEAR})")

            # Anachronistic terms in old papers
            if year < 2000:
                title_lower = clean_title.lower()
                for term in ANACHRONISTIC_TERMS:
                    if term in title_lower:
                        issues.append(
                            f"Anachronistic: pre-2000 ({year}) paper mentions '{term}'"
                        )
                        break  # one flag is enough

    # --- Unverifiable entry ---
    doi = entry.get("doi", "")
    url = entry.get("url", "")
    if not doi and not url:
        issues.append("No DOI and no URL -- cannot independently verify")

    return issues


# ---------------------------------------------------------------------------
# Main Verifier Class
# ---------------------------------------------------------------------------

class BibtexCitationVerifier:
    """
    Verify BibTeX citations in a LaTeX manuscript project.

    Workflow:
        1. Parse .bib file
        2. Scan .tex files for \\cite{} references
        3. Cross-check cited keys vs. .bib keys
        4. For each .bib entry: hallucination patterns, DOI check, URL check
        5. Produce a verification report
    """

    # Status constants
    VERIFIED = "VERIFIED"
    URL_VERIFIED = "URL_VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    UNVERIFIED = "UNVERIFIED"

    def __init__(
        self,
        bib_path: Path,
        tex_dir: Path,
        strict: bool = False,
        output_path: Optional[Path] = None,
    ):
        self.bib_path = bib_path
        self.tex_dir = tex_dir
        self.strict = strict
        self.output_path = output_path

        # Will be populated during verification
        self.entries: Dict[str, Dict[str, str]] = {}
        self.cited_keys: Set[str] = set()
        self.key_to_files: Dict[str, List[str]] = {}
        self.results: Dict[str, Dict] = {}  # key -> verification result
        self.missing_keys: Set[str] = set()  # cited but not in .bib
        self.orphan_keys: Set[str] = set()   # in .bib but not cited

        self._report_lines: List[str] = []

    # ---- Output helpers ----

    def _out(self, line: str = "") -> None:
        """Print and buffer a line for the report."""
        print(line)
        self._report_lines.append(line)

    def _separator(self, char: str = "=", width: int = 70) -> None:
        self._out(char * width)

    # ---- Core workflow ----

    def run(self) -> bool:
        """
        Execute the full verification pipeline.

        Returns True if verification passed, False if failed.
        """
        self._separator()
        self._out("BIBTEX CITATION VERIFICATION REPORT")
        self._out(f"  .bib file : {self.bib_path}")
        self._out(f"  .tex dir  : {self.tex_dir}")
        self._out(f"  strict    : {self.strict}")
        self._out(f"  timestamp : {time.strftime('%Y-%m-%d %H:%M:%S')}")
        self._separator()
        self._out()

        # Step 1: Parse .bib
        self._step_parse_bib()

        # Step 2: Scan .tex
        self._step_scan_tex()

        # Step 3: Cross-reference
        self._step_cross_reference()

        # Step 4: Verify each entry
        self._step_verify_entries()

        # Step 5: Summary
        passed = self._step_summary()

        # Save report if requested
        if self.output_path:
            self._save_report()

        return passed

    def _step_parse_bib(self) -> None:
        self._out("[1/5] Parsing BibTeX file")
        self._out(f"      {self.bib_path}")

        try:
            bib_text = self.bib_path.read_text(encoding="utf-8")
        except Exception as e:
            self._out(f"  ERROR: Cannot read .bib file: {e}")
            sys.exit(1)

        self.entries = parse_bibtex(bib_text)
        self._out(f"      Found {len(self.entries)} entries")

        # List them
        for key, fields in self.entries.items():
            etype = fields.get("_type", "?")
            title = fields.get("title", "(no title)")[:70]
            self._out(f"        @{etype}{{{key}}} -- {title}")
        self._out()

    def _step_scan_tex(self) -> None:
        self._out("[2/5] Scanning .tex files for citations")
        self._out(f"      {self.tex_dir}")

        self.cited_keys, self.key_to_files = scan_tex_citations(self.tex_dir)
        self._out(f"      Found {len(self.cited_keys)} unique citation keys")

        tex_files = sorted(self.tex_dir.rglob("*.tex"))
        self._out(f"      Scanned {len(tex_files)} .tex files")
        for tf in tex_files:
            self._out(f"        {tf.relative_to(self.tex_dir)}")
        self._out()

    def _step_cross_reference(self) -> None:
        self._out("[3/5] Cross-referencing citations vs. BibTeX entries")

        bib_keys = set(self.entries.keys())

        self.missing_keys = self.cited_keys - bib_keys
        self.orphan_keys = bib_keys - self.cited_keys

        if self.missing_keys:
            self._out(f"      MISSING from .bib ({len(self.missing_keys)}):")
            for k in sorted(self.missing_keys):
                files = self.key_to_files.get(k, [])
                self._out(f"        \\cite{{{k}}}  (used in: {', '.join(sorted(set(files)))})")
        else:
            self._out("      All cited keys found in .bib")

        if self.orphan_keys:
            self._out(f"      ORPHAN .bib entries not cited ({len(self.orphan_keys)}):")
            for k in sorted(self.orphan_keys):
                self._out(f"        {k}")
        else:
            self._out("      No orphan .bib entries")

        self._out()

    def _step_verify_entries(self) -> None:
        self._out("[4/5] Verifying BibTeX entries")
        self._separator("-")

        total = len(self.entries)
        for idx, (key, fields) in enumerate(self.entries.items(), 1):
            self._out(f"\n  [{idx}/{total}] {key}")
            title = fields.get("title", "(no title)")
            # Clean LaTeX for display
            disp_title = re.sub(r"[{}]", "", title)[:80]
            self._out(f"    Title : {disp_title}")
            self._out(f"    Year  : {fields.get('year', '?')}")
            self._out(f"    Type  : @{fields.get('_type', '?')}")

            result: Dict = {
                "key": key,
                "status": self.UNVERIFIED,
                "issues": [],
                "doi_verified": False,
                "url_verified": False,
                "doi_metadata": {},
            }

            # 4a. Hallucination pattern detection
            h_issues = detect_hallucination_patterns(fields)
            if h_issues:
                result["issues"].extend(h_issues)
                for issue in h_issues:
                    self._out(f"    [!] {issue}")

            # 4b. DOI verification
            doi = fields.get("doi", "")
            if doi:
                self._out(f"    DOI   : {doi}")
                self._out(f"    Resolving DOI ...", )
                success, metadata = verify_doi(doi)
                time.sleep(0.5)  # rate limit

                if success:
                    result["doi_verified"] = True
                    result["doi_metadata"] = metadata
                    result["status"] = self.VERIFIED
                    self._out(f"    DOI resolved successfully")

                    # Check title similarity
                    if title and metadata.get("title"):
                        sim = title_similarity(title, metadata["title"])
                        self._out(f"    Title similarity: {sim:.1%}")
                        if sim < 0.4:
                            issue = (
                                f"Title mismatch: similarity {sim:.1%} "
                                f"(DOI title: '{metadata['title'][:60]}...')"
                            )
                            result["issues"].append(issue)
                            result["status"] = self.SUSPICIOUS
                            self._out(f"    [!] {issue}")

                    # Check year match
                    bib_year = fields.get("year", "")
                    doi_year = metadata.get("year")
                    if bib_year and doi_year:
                        try:
                            if int(bib_year) != int(doi_year):
                                issue = f"Year mismatch: .bib says {bib_year}, DOI says {doi_year}"
                                result["issues"].append(issue)
                                result["status"] = self.SUSPICIOUS
                                self._out(f"    [!] {issue}")
                        except ValueError:
                            pass
                else:
                    err = metadata.get("error", "unknown error")
                    result["issues"].append(f"DOI resolution failed: {err}")
                    self._out(f"    [X] DOI resolution failed: {err}")
            else:
                self._out(f"    DOI   : (none)")

            # 4c. URL verification
            url = fields.get("url", "")
            if url:
                self._out(f"    URL   : {url}")
                accessible, status_msg = verify_url(url)
                time.sleep(0.5)  # rate limit

                if accessible:
                    result["url_verified"] = True
                    self._out(f"    URL accessible: {status_msg}")
                    # Upgrade from UNVERIFIED if DOI was absent
                    if result["status"] == self.UNVERIFIED:
                        result["status"] = self.URL_VERIFIED
                else:
                    result["issues"].append(f"URL inaccessible: {status_msg}")
                    self._out(f"    [X] URL inaccessible: {status_msg}")
            else:
                self._out(f"    URL   : (none)")

            # 4d. Determine final status
            # If hallucination issues were found but DOI verified cleanly, trust DOI
            if result["doi_verified"] and not any(
                "mismatch" in i.lower() for i in result["issues"]
            ):
                # DOI verification overrides pattern-based suspicion
                # (except for metadata mismatches which indicate real problems)
                has_only_soft_issues = all(
                    "No DOI" in i or "cannot independently" in i
                    for i in result["issues"]
                )
                if has_only_soft_issues or not result["issues"]:
                    result["status"] = self.VERIFIED

            if not result["doi_verified"] and not result["url_verified"]:
                if result["issues"]:
                    result["status"] = self.SUSPICIOUS
                else:
                    result["status"] = self.UNVERIFIED

            status_display = {
                self.VERIFIED: "VERIFIED (DOI)",
                self.URL_VERIFIED: "VERIFIED (URL)",
                self.SUSPICIOUS: "SUSPICIOUS",
                self.UNVERIFIED: "UNVERIFIED",
            }
            self._out(f"    => Status: {status_display.get(result['status'], result['status'])}")

            self.results[key] = result

        self._out()

    def _step_summary(self) -> bool:
        """Print summary and return True if passed, False if failed."""
        self._separator()
        self._out("VERIFICATION SUMMARY")
        self._separator()
        self._out()

        verified = [k for k, r in self.results.items() if r["status"] == self.VERIFIED]
        url_verified = [k for k, r in self.results.items() if r["status"] == self.URL_VERIFIED]
        suspicious = [k for k, r in self.results.items() if r["status"] == self.SUSPICIOUS]
        unverified = [k for k, r in self.results.items() if r["status"] == self.UNVERIFIED]

        total = len(self.results)
        self._out(f"  Total .bib entries   : {total}")
        self._out(f"  DOI verified         : {len(verified)}")
        self._out(f"  URL verified         : {len(url_verified)}")
        self._out(f"  Suspicious           : {len(suspicious)}")
        self._out(f"  Unverified           : {len(unverified)}")
        self._out(f"  Missing from .bib    : {len(self.missing_keys)}")
        self._out(f"  Orphan .bib entries  : {len(self.orphan_keys)}")
        self._out()

        # Detail suspicious entries
        if suspicious:
            self._out("SUSPICIOUS ENTRIES (manual review needed):")
            for k in suspicious:
                r = self.results[k]
                self._out(f"  {k}:")
                for issue in r["issues"]:
                    self._out(f"    - {issue}")
            self._out()

        # Detail unverified entries
        if unverified:
            self._out("UNVERIFIED ENTRIES (could not check):")
            for k in unverified:
                r = self.results[k]
                issues = r["issues"]
                self._out(f"  {k}: {issues[0] if issues else 'no DOI or URL'}")
            self._out()

        # Detail missing keys
        if self.missing_keys:
            self._out("MISSING KEYS (cited in .tex but not in .bib):")
            for k in sorted(self.missing_keys):
                files = self.key_to_files.get(k, [])
                self._out(f"  \\cite{{{k}}}  in: {', '.join(sorted(set(files)))}")
            self._out()

        # Detail orphan keys
        if self.orphan_keys:
            self._out("ORPHAN ENTRIES (in .bib but never cited):")
            for k in sorted(self.orphan_keys):
                self._out(f"  {k}")
            self._out()

        # ---- Pass / Fail decision ----
        self._separator()
        failed = False
        reasons: List[str] = []

        if self.missing_keys:
            reasons.append(f"{len(self.missing_keys)} citation key(s) missing from .bib")
            failed = True

        if suspicious:
            reasons.append(f"{len(suspicious)} suspicious entry/entries detected")
            if self.strict:
                failed = True

        if unverified and self.strict:
            reasons.append(f"{len(unverified)} unverified entry/entries (strict mode)")
            failed = True

        total_ok = len(verified) + len(url_verified)
        if total > 0 and total_ok / total < 0.5 and not self.strict:
            reasons.append(f"Less than 50% of entries verified ({total_ok}/{total})")
            # Warning, but not a hard fail in non-strict mode

        if failed:
            self._out("RESULT: FAILED")
            for r in reasons:
                self._out(f"  - {r}")
        elif reasons:
            self._out("RESULT: PASSED (with warnings)")
            for r in reasons:
                self._out(f"  - {r}")
        else:
            self._out("RESULT: PASSED")
            self._out(f"  {total_ok}/{total} entries independently verified")

        self._separator()
        self._out()

        return not failed

    def _save_report(self) -> None:
        """Write the buffered report to the output file."""
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text("\n".join(self._report_lines) + "\n", encoding="utf-8")
            print(f"Report saved to: {self.output_path}")
        except Exception as e:
            print(f"ERROR: Could not save report: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify BibTeX citations in a LaTeX manuscript project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s --bib references.bib --tex-dir sections/
  %(prog)s --bib refs.bib --tex-dir . --strict --output report.txt

Checks performed:
  - Parse .bib and extract all entries
  - Scan .tex files for \\cite{} commands
  - Cross-check: missing keys, orphan entries
  - DOI resolution and metadata matching (title similarity, year)
  - URL accessibility (HEAD request)
  - Hallucination pattern detection (generic titles, future years,
    anachronistic terms, missing fields, unverifiable entries)

Exit codes:
  0 = passed (possibly with warnings)
  1 = failed (missing keys, suspicious entries in strict mode, etc.)

Requires only Python 3.10+ stdlib. No external packages needed.
""",
    )

    parser.add_argument(
        "--bib",
        type=str,
        required=True,
        help="Path to the .bib file (e.g., references.bib)",
    )
    parser.add_argument(
        "--tex-dir",
        type=str,
        required=True,
        help="Directory containing .tex files to scan (searched recursively)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: fail on any suspicious or unverified entries",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Save verification report to this file path",
    )

    args = parser.parse_args()

    bib_path = Path(args.bib)
    tex_dir = Path(args.tex_dir)

    if not bib_path.exists():
        print(f"ERROR: .bib file not found: {bib_path}", file=sys.stderr)
        sys.exit(1)
    if not tex_dir.is_dir():
        print(f"ERROR: .tex directory not found: {tex_dir}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else None

    verifier = BibtexCitationVerifier(
        bib_path=bib_path,
        tex_dir=tex_dir,
        strict=args.strict,
        output_path=output_path,
    )

    passed = verifier.run()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
