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
from urllib.parse import quote, urlencode


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
# Supports up to 3 levels of brace nesting (needed for LaTeX accents like {\"{u}})
_FIELD_RE = re.compile(
    r"(\w+)\s*=\s*(?:\{((?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*)\}|\"([^\"]*)\"|(\d+))",
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
    Similarity on lowercased word sets (punctuation stripped).
    Uses max(Jaccard, containment) to handle cases where one title
    is a substring/abbreviation of the other (e.g., DOI returns
    "Shredder" instead of "Shredder: Learning Noise Distributions...").
    Returns 0.0 -- 1.0.
    """
    def normalize(s: str) -> Set[str]:
        s = re.sub(r"[^\w\s]", " ", s.lower())
        return {w for w in s.split() if len(w) > 1}

    w1, w2 = normalize(t1), normalize(t2)
    if not w1 or not w2:
        return 0.0
    intersection = len(w1 & w2)
    jaccard = intersection / len(w1 | w2)
    # Containment: fraction of the SMALLER set that appears in the larger
    containment = intersection / min(len(w1), len(w2))
    return max(jaccard, containment)


# ---------------------------------------------------------------------------
# Crossref Lookup (primary — 50 req/sec, no API key needed)
# ---------------------------------------------------------------------------

CROSSREF_API_BASE = "https://api.crossref.org/works"


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None,
                   retries: int = 3) -> Optional[Dict]:
    """Generic HTTP GET returning parsed JSON, with retry on 429."""
    for attempt in range(retries):
        req = request.Request(url)
        req.add_header("User-Agent", "BibTeX-Citation-Verifier/2.0 (mailto:verify@example.com)")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 3 * (attempt + 1)
                time.sleep(wait)
                continue
            return None
        except (error.URLError, Exception):
            return None
    return None


def _clean_latex_title(title: str) -> str:
    """Strip LaTeX markup from a title for search queries."""
    clean = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)
    clean = re.sub(r"[{}]", "", clean).strip()
    return clean


def search_crossref(title: str) -> Tuple[bool, Dict]:
    """
    Search Crossref by bibliographic query. Return the best title match.

    Rate limit: 50 req/sec in polite pool (identified by User-Agent with mailto:).
    Returns (found, metadata_dict) with source="crossref".
    """
    clean = _clean_latex_title(title)
    if not clean:
        return False, {"error": "empty title after cleanup"}

    params = urlencode({"query.bibliographic": clean, "rows": "5",
                        "select": "title,author,published-print,published-online,"
                                  "container-title,DOI,type"})
    url = f"{CROSSREF_API_BASE}?{params}"

    data = _http_get_json(url)
    if not data or "message" not in data:
        return False, {"error": "no response from Crossref"}

    items = data["message"].get("items", [])
    if not items:
        return False, {"error": "no results from Crossref"}

    # Find best match by title similarity
    best_sim = 0.0
    best_item = None
    for item in items:
        cr_titles = item.get("title", [])
        cr_title = cr_titles[0] if cr_titles else ""
        sim = title_similarity(clean, cr_title)
        if sim > best_sim:
            best_sim = sim
            best_item = item

    if best_item is None or best_sim < 0.5:
        return False, {"error": f"no good title match (best similarity: {best_sim:.1%})"}

    # Extract authors
    authors = []
    for a in best_item.get("author", []):
        name = f"{a.get('given', '')} {a.get('family', '')}".strip()
        if name:
            authors.append(name)

    # Extract year from published-print or published-online
    year = None
    for date_field in ("published-print", "published-online"):
        date_parts = best_item.get(date_field, {}).get("date-parts", [[None]])
        if date_parts and date_parts[0] and date_parts[0][0]:
            year = date_parts[0][0]
            break

    # Extract venue
    containers = best_item.get("container-title", [])
    venue = containers[0] if containers else ""

    cr_titles = best_item.get("title", [])
    return True, {
        "title": cr_titles[0] if cr_titles else "",
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": best_item.get("DOI", ""),
        "source": "crossref",
        "title_similarity": best_sim,
    }


# ---------------------------------------------------------------------------
# Semantic Scholar Lookup (fallback — 100 req/5min, restrictive)
# ---------------------------------------------------------------------------

S2_API_BASE = "https://api.semanticscholar.org/graph/v1/paper"
S2_SEARCH_FIELDS = "title,authors,year,venue,externalIds"


def search_semantic_scholar(
    title: str, api_key: Optional[str] = None
) -> Tuple[bool, Dict]:
    """
    Search Semantic Scholar by title. Return the best match.
    Used as fallback when Crossref returns no results.

    Free tier: 100 requests / 5 minutes (no API key needed).
    Returns (found, metadata_dict) with source="s2".
    """
    clean = _clean_latex_title(title)
    if not clean:
        return False, {"error": "empty title after cleanup"}

    params = urlencode({"query": clean, "limit": "5", "fields": S2_SEARCH_FIELDS})
    url = f"{S2_API_BASE}/search?{params}"

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    data = _http_get_json(url, headers=headers)
    if not data or not data.get("data"):
        return False, {"error": "no results from Semantic Scholar"}

    # Find best match by title similarity
    best_sim = 0.0
    best_paper = None
    for paper in data["data"]:
        s2_title = paper.get("title", "")
        sim = title_similarity(clean, s2_title)
        if sim > best_sim:
            best_sim = sim
            best_paper = paper

    if best_paper is None or best_sim < 0.5:
        return False, {"error": f"no good title match (best similarity: {best_sim:.1%})"}

    authors = [a.get("name", "") for a in best_paper.get("authors", [])]
    return True, {
        "title": best_paper.get("title", ""),
        "authors": authors,
        "year": best_paper.get("year"),
        "venue": best_paper.get("venue", ""),
        "doi": best_paper.get("externalIds", {}).get("DOI", ""),
        "source": "s2",
        "title_similarity": best_sim,
    }


def search_external(title: str, enable_s2: bool = True,
                    s2_api_key: Optional[str] = None,
                    bib_author: str = "") -> Tuple[bool, Dict]:
    """
    Search for a paper by title. Crossref first, S2 as fallback.
    Returns (found, metadata_dict). metadata["source"] indicates which API matched.

    If bib_author is provided, a Crossref match with 0% author overlap is rejected
    (likely a different paper with a similar title) and S2 is tried instead.
    """
    found, meta = search_crossref(title)
    if found and bib_author and meta.get("authors"):
        # Validate: reject if zero author overlap (wrong paper)
        bib_lasts = set(parse_bib_authors(bib_author))
        api_lasts = set(parse_s2_authors(meta["authors"]))
        if bib_lasts and api_lasts and len(bib_lasts & api_lasts) == 0:
            # No author overlap — likely wrong paper, try S2
            found = False
            meta["error"] = "Crossref match rejected (0% author overlap)"
    if found:
        return found, meta

    if enable_s2:
        time.sleep(3.0)  # conservative rate limit for S2
        return search_semantic_scholar(title, s2_api_key)

    return False, meta  # return Crossref's error


def parse_bib_authors(bib_author: str) -> List[str]:
    """
    Parse BibTeX author field into a list of normalized last names.

    Handles formats:
      "Last, First and Last, First"
      "First Last and First Last"
      "Last, First Middle and Last, First"
    """
    if not bib_author:
        return []
    # Split on " and " (BibTeX author separator)
    parts = re.split(r"\s+and\s+", bib_author, flags=re.IGNORECASE)
    last_names = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Strip LaTeX accents: {\"o} -> o, {\c{c}} -> c, etc.
        part = re.sub(r"\{?\\['\"`~^=.cuvHtdb]\{?(\w)\}?\}?", r"\1", part)
        part = re.sub(r"[{}]", "", part)
        if "," in part:
            # "Last, First" format
            last = part.split(",")[0].strip()
        else:
            # "First Last" format — last word is the last name
            words = part.split()
            last = words[-1] if words else part
        last_names.append(last.lower().strip())
    return last_names


def _strip_diacritics(s: str) -> str:
    """Remove diacritics: ü→u, ç→c, ö→o, etc."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def parse_s2_authors(s2_authors: List[str]) -> List[str]:
    """Extract normalized last names from external API author name list."""
    last_names = []
    for name in s2_authors:
        name = name.strip()
        if not name:
            continue
        words = name.split()
        last = words[-1].lower() if words else name.lower()
        last_names.append(_strip_diacritics(last))
    return last_names


def author_similarity(bib_author: str, s2_authors: List[str]) -> Tuple[float, List[str]]:
    """
    Compare BibTeX author string against S2 author list.

    Returns (similarity_score, list_of_mismatches).
    Similarity is Jaccard on last-name sets.
    """
    bib_lasts = set(parse_bib_authors(bib_author))
    s2_lasts = set(parse_s2_authors(s2_authors))

    if not bib_lasts and not s2_lasts:
        return 1.0, []
    if not bib_lasts or not s2_lasts:
        return 0.0, [f"bib={list(bib_lasts)}, s2={list(s2_lasts)}"]

    intersection = bib_lasts & s2_lasts
    union = bib_lasts | s2_lasts
    sim = len(intersection) / len(union) if union else 0.0

    mismatches = []
    only_bib = bib_lasts - s2_lasts
    only_s2 = s2_lasts - bib_lasts
    if only_bib:
        mismatches.append(f"in bib only: {sorted(only_bib)}")
    if only_s2:
        mismatches.append(f"in S2 only: {sorted(only_s2)}")

    return sim, mismatches


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
    S2_VERIFIED = "S2_VERIFIED"
    URL_VERIFIED = "URL_VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    UNVERIFIED = "UNVERIFIED"

    def __init__(
        self,
        bib_path: Path,
        tex_dir: Path,
        strict: bool = False,
        output_path: Optional[Path] = None,
        enable_s2: bool = True,
        s2_api_key: Optional[str] = None,
    ):
        self.bib_path = bib_path
        self.tex_dir = tex_dir
        self.strict = strict
        self.output_path = output_path
        self.enable_s2 = enable_s2
        self.s2_api_key = s2_api_key

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

            # 4d. External API cross-verification (Crossref primary, S2 fallback)
            result["ext_verified"] = False
            result["ext_metadata"] = {}
            if title:
                self._out(f"    API   : Searching Crossref ...")
                found, ext_meta = search_external(
                    title, enable_s2=self.enable_s2, s2_api_key=self.s2_api_key,
                    bib_author=fields.get("author", ""),
                )
                src = ext_meta.get("source", "?")
                src_label = "Crossref" if src == "crossref" else "S2"

                if found:
                    result["ext_metadata"] = ext_meta
                    sim_pct = ext_meta.get("title_similarity", 0)
                    self._out(f"    {src_label:8s}: Match found (title similarity: {sim_pct:.0%})")
                    self._out(f"    {src_label:8s}: \"{ext_meta.get('title', '')[:70]}\"")

                    # Author cross-check
                    author = fields.get("author", "")
                    ext_authors = ext_meta.get("authors", [])
                    if author and ext_authors:
                        auth_sim, auth_mismatches = author_similarity(author, ext_authors)
                        self._out(f"    {src_label} authors: similarity {auth_sim:.0%}")
                        if auth_sim < 0.5:
                            issue = f"Author mismatch ({src_label}): {'; '.join(auth_mismatches)}"
                            result["issues"].append(issue)
                            self._out(f"    [!] {issue}")

                    # Year cross-check
                    ext_year = ext_meta.get("year")
                    bib_year_str = fields.get("year", "")
                    if bib_year_str and ext_year:
                        try:
                            if int(bib_year_str) != int(ext_year):
                                issue = f"Year mismatch ({src_label}): bib={bib_year_str}, {src_label}={ext_year}"
                                result["issues"].append(issue)
                                self._out(f"    [!] {issue}")
                        except (ValueError, TypeError):
                            pass

                    # Venue cross-check
                    ext_venue = ext_meta.get("venue", "")
                    bib_venue = fields.get("booktitle", "") or fields.get("journal", "")
                    if ext_venue and bib_venue:
                        venue_sim = title_similarity(bib_venue, ext_venue)
                        self._out(f"    {src_label} venue: \"{ext_venue}\" (similarity: {venue_sim:.0%})")
                        if venue_sim < 0.3:
                            issue = (
                                f"Venue mismatch ({src_label}): "
                                f"bib=\"{bib_venue[:50]}\", {src_label}=\"{ext_venue[:50]}\""
                            )
                            result["issues"].append(issue)
                            self._out(f"    [!] {issue}")

                    # Ext verified if no mismatch issues from this step
                    ext_issues = [i for i in result["issues"]
                                  if "(Crossref)" in i or "(S2)" in i]
                    if not ext_issues:
                        result["ext_verified"] = True
                else:
                    err = ext_meta.get("error", "unknown")
                    self._out(f"    API   : {err}")

            # 4e. Determine final status
            # Priority: DOI > External API (Crossref/S2) > URL > pattern-based
            ext_src = result.get("ext_metadata", {}).get("source", "s2")
            ext_label = "Crossref" if ext_src == "crossref" else "Semantic Scholar"

            if result["doi_verified"] and not any(
                "mismatch" in i.lower() for i in result["issues"]
            ):
                has_only_soft_issues = all(
                    "No DOI" in i or "cannot independently" in i
                    for i in result["issues"]
                )
                if has_only_soft_issues or not result["issues"]:
                    result["status"] = self.VERIFIED
            elif result["ext_verified"] and not any(
                "mismatch" in i.lower() for i in result["issues"]
            ):
                result["status"] = self.S2_VERIFIED  # reuse constant for ext-verified

            # Downgrade to SUSPICIOUS if any mismatch found (even with DOI/ext)
            if any("mismatch" in i.lower() for i in result["issues"]):
                result["status"] = self.SUSPICIOUS

            if not result["doi_verified"] and not result["url_verified"] and not result["ext_verified"]:
                if result["issues"]:
                    result["status"] = self.SUSPICIOUS
                else:
                    result["status"] = self.UNVERIFIED

            status_display = {
                self.VERIFIED: "VERIFIED (DOI)",
                self.S2_VERIFIED: f"VERIFIED ({ext_label})",
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
        ext_verified = [k for k, r in self.results.items() if r["status"] == self.S2_VERIFIED]
        url_verified = [k for k, r in self.results.items() if r["status"] == self.URL_VERIFIED]
        suspicious = [k for k, r in self.results.items() if r["status"] == self.SUSPICIOUS]
        unverified = [k for k, r in self.results.items() if r["status"] == self.UNVERIFIED]

        # Count by source for ext-verified
        cr_count = sum(1 for k in ext_verified
                       if self.results[k].get("ext_metadata", {}).get("source") == "crossref")
        s2_count = len(ext_verified) - cr_count

        total = len(self.results)
        self._out(f"  Total .bib entries   : {total}")
        self._out(f"  DOI verified         : {len(verified)}")
        self._out(f"  Crossref verified    : {cr_count}")
        self._out(f"  S2 verified          : {s2_count}")
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

        total_ok = len(verified) + len(ext_verified) + len(url_verified)
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
    parser.add_argument(
        "--no-s2",
        action="store_true",
        help="Disable Semantic Scholar lookup (for offline use)",
    )
    parser.add_argument(
        "--s2-key",
        type=str,
        default=None,
        help="Semantic Scholar API key (optional, relaxes rate limits)",
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
        enable_s2=not args.no_s2,
        s2_api_key=args.s2_key,
    )

    passed = verifier.run()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
