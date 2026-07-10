#!/usr/bin/env python3
"""
BibTeX Citation Verification Script

Adapted from deep-research verify_citations.py for LaTeX manuscript projects.
Verifies BibTeX entries by agreement with DOI, Crossref, or Semantic Scholar
metadata; cross-references .tex citations with .bib entries; and detects
common LLM hallucination patterns in fabricated references. BibTeX URLs are
reported as informational fields and are never fetched as verification proof.

Usage:
    python verify_citations_bibtex.py --bib references.bib --tex-dir sections/
    python verify_citations_bibtex.py --bib references.bib --tex-dir sections/ --strict
    python verify_citations_bibtex.py --bib references.bib --tex-dir sections/ --output report.txt

Requires only Python 3.10+ stdlib (no external dependencies).
"""

import sys
import argparse
import datetime
import os
import re
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib import request, error
import unicodedata
from urllib.parse import quote, urlencode


# ---------------------------------------------------------------------------
# HTTP identification (Crossref polite pool + doi.org)
# ---------------------------------------------------------------------------

# Contact for the Crossref polite pool. Set via --mailto flag or the
# CROSSREF_MAILTO environment variable; if neither is set, the mailto
# clause is omitted entirely (anonymous pool).
_mailto_contact: Optional[str] = None


def set_mailto(contact: Optional[str]) -> None:
    """Set the Crossref polite-pool contact (from the --mailto flag)."""
    global _mailto_contact
    _mailto_contact = contact


def _user_agent() -> str:
    """Build the User-Agent string, including mailto: only if configured."""
    contact = _mailto_contact or os.environ.get("CROSSREF_MAILTO")
    if contact:
        return f"BibTeX-Citation-Verifier/2.0 (mailto:{contact})"
    return "BibTeX-Citation-Verifier/2.0"


def resolve_s2_key(cli_value: Optional[str]) -> Optional[str]:
    """Resolve the Semantic Scholar API key: --s2-key flag, then S2_API_KEY env."""
    return cli_value or os.environ.get("S2_API_KEY") or None


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

_FIELD_NAME_RE = re.compile(r"[A-Za-z][\w\-]*")


def _parse_fields(
    body: str,
    key: str = "",
    warnings: Optional[List[str]] = None,
) -> Dict[str, str]:
    """
    Tokenize a BibTeX entry body into fields using brace-depth counting.

    Handles arbitrary brace nesting in {...} values, escaped quotes (\\")
    in "..." values, bare numbers, and unexpanded @string macro references
    (warned and skipped, never silently dropped).
    """
    fields: Dict[str, str] = {}
    pos = 0
    n = len(body)

    while pos < n:
        # Skip whitespace and field separators
        while pos < n and (body[pos].isspace() or body[pos] == ","):
            pos += 1
        if pos >= n:
            break

        # Field name
        m = _FIELD_NAME_RE.match(body, pos)
        if not m:
            pos += 1
            continue
        fname = m.group(0).lower()
        pos = m.end()

        # Expect '='
        while pos < n and body[pos].isspace():
            pos += 1
        if pos >= n or body[pos] != "=":
            continue  # stray token, not a field assignment
        pos += 1
        while pos < n and body[pos].isspace():
            pos += 1
        if pos >= n:
            break

        c = body[pos]
        if c == "{":
            # Brace-delimited value: count depth until the matching '}'
            depth = 1
            pos += 1
            start = pos
            while pos < n and depth > 0:
                if body[pos] == "{":
                    depth += 1
                elif body[pos] == "}":
                    depth -= 1
                pos += 1
            fval = body[start : pos - 1]
        elif c == '"':
            # Quote-delimited value: honor escaped quotes (\")
            pos += 1
            chars: List[str] = []
            while pos < n:
                ch = body[pos]
                if ch == "\\" and pos + 1 < n:
                    chars.append(body[pos : pos + 2])
                    pos += 2
                    continue
                if ch == '"':
                    break
                chars.append(ch)
                pos += 1
            fval = "".join(chars)
            pos += 1  # skip closing quote
        else:
            # Bare value: a number, or an unexpanded @string macro reference
            m2 = re.match(r"[^,\n]+", body[pos:])
            raw = m2.group(0).strip() if m2 else ""
            pos += m2.end() if m2 else 1
            if re.fullmatch(r"\d+", raw):
                fval = raw
            else:
                if warnings is not None and raw:
                    warnings.append(
                        f"Entry '{key}': field '{fname}' references unexpanded "
                        f"@string macro '{raw}' -- field skipped"
                    )
                continue

        # Collapse internal whitespace
        fval = re.sub(r"\s+", " ", fval).strip()
        fields[fname] = fval

    return fields


def parse_bibtex(
    text: str, warnings: Optional[List[str]] = None
) -> Dict[str, Dict[str, str]]:
    """
    Parse BibTeX source text into a dict keyed by citation key.

    Each value is a dict with keys:
        _type   : entry type (article, inproceedings, ...)
        _key    : citation key
        title, author, year, doi, url, booktitle, journal, ... (as present)

    Field values have outer braces / quotes stripped but inner LaTeX is kept.
    If a `warnings` list is provided, non-fatal parse problems (duplicate
    keys, unexpanded @string macros) are appended to it.
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

        if key in entries:
            if warnings is not None:
                warnings.append(
                    f"Duplicate entry key '{key}' -- keeping first occurrence"
                )
            continue

        # Extract fields from the body
        fields: Dict[str, str] = {"_type": entry_type, "_key": key}
        fields.update(_parse_fields(body, key=key, warnings=warnings))

        entries[key] = fields

    return entries


# ---------------------------------------------------------------------------
# LaTeX Citation Scanner
# ---------------------------------------------------------------------------

# Matches \cite{...}, \citep{...}, \citet{...}, \citeauthor{...}, including
# starred forms (\citet*{...}) and optional [...] arguments, possibly multiple
# (e.g. \citep[e.g.][]{key}, \cite[p.~3]{key}).
_CITE_RE = re.compile(r"\\[Cc]ite[a-zA-Z]*\*?\s*(?:\[[^\]]*\]\s*)*\{([^}]+)\}")


def _strip_tex_comments(text: str) -> str:
    """Remove LaTeX line comments (% to end of line), respecting escaped \\%."""
    stripped_lines: List[str] = []
    for line in text.split("\n"):
        out: List[str] = []
        i = 0
        while i < len(line):
            if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
                break
            out.append(line[i])
            i += 1
        stripped_lines.append("".join(out))
    return "\n".join(stripped_lines)


def scan_tex_citations(
    tex_dir: Path,
) -> Tuple[Set[str], Dict[str, List[str]], List[str]]:
    """
    Scan all .tex files under tex_dir (recursively) for \\cite commands.
    LaTeX comments are stripped before matching.

    Returns:
        cited_keys : set of all citation keys referenced
        key_to_files: dict mapping each key to list of files where it appears
        warnings   : list of warnings (e.g., unreadable files)
    """
    cited_keys: Set[str] = set()
    key_to_files: Dict[str, List[str]] = {}
    warnings: List[str] = []

    tex_files = sorted(tex_dir.rglob("*.tex"))
    if not tex_files:
        return cited_keys, key_to_files, warnings

    for tf in tex_files:
        try:
            content = tf.read_text(encoding="utf-8")
        except Exception as e:
            warnings.append(f"Cannot read .tex file {tf}: {e}")
            continue

        content = _strip_tex_comments(content)

        for m in _CITE_RE.finditer(content):
            # Handle multi-key citations: \cite{key1,key2,key3}
            raw_keys = m.group(1)
            for k in raw_keys.split(","):
                k = k.strip()
                if k:
                    cited_keys.add(k)
                    key_to_files.setdefault(k, []).append(str(tf.relative_to(tex_dir)))

    return cited_keys, key_to_files, warnings


# ---------------------------------------------------------------------------
# Verification Helpers
# ---------------------------------------------------------------------------

def verify_doi(doi: str, retries: int = 3) -> Tuple[bool, Dict]:
    """
    Resolve a DOI via https://doi.org/ with CSL-JSON content negotiation.

    Transient failures (URLError, timeout, HTTP 5xx/429) are retried up to
    `retries` times with exponential backoff. A persistent network failure
    is reported with metadata["network_error"] = True (retryable later);
    an HTTP 404 means the DOI does not exist and is NOT retried.

    Returns (success, metadata_dict).
    On success, metadata_dict contains title, year, authors, venue.
    On failure, metadata_dict contains an 'error' key.
    """
    url = f"https://doi.org/{quote(doi, safe='/')}"
    last_err = "unknown error"

    for attempt in range(retries):
        req = request.Request(url)
        req.add_header("Accept", "application/vnd.citationstyles.csl+json")
        req.add_header("User-Agent", _user_agent())

        try:
            with request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                return False, {"error": f"invalid JSON from doi.org: {str(e)[:80]}"}
            if not isinstance(data, dict):
                data = {}

            year = None
            issued = data.get("issued")
            if isinstance(issued, dict):
                date_parts = issued.get("date-parts")
                if (
                    isinstance(date_parts, list)
                    and date_parts
                    and isinstance(date_parts[0], (list, tuple))
                    and date_parts[0]
                ):
                    candidate_year = date_parts[0][0]
                    if isinstance(candidate_year, int) and not isinstance(
                        candidate_year, bool
                    ):
                        year = candidate_year
                    elif (
                        isinstance(candidate_year, str)
                        and candidate_year.isascii()
                        and candidate_year.isdigit()
                    ):
                        year = int(candidate_year)

            authors = []
            raw_authors = data.get("author", [])
            if isinstance(raw_authors, list):
                for author in raw_authors:
                    if not isinstance(author, dict):
                        continue
                    given = author.get("given", "")
                    family = author.get("family", "")
                    given = given.strip() if isinstance(given, str) else ""
                    family = family.strip() if isinstance(family, str) else ""
                    name = f"{given} {family}".strip()
                    if name:
                        authors.append(name)
            return True, {
                "title": _optional_metadata_string(data.get("title", "")),
                "year": year,
                "authors": authors,
                "venue": _optional_metadata_string(
                    data.get("container-title", "")
                ),
            }
        except error.HTTPError as e:
            code = e.code
            e.close()
            if code == 404:
                return False, {"error": "DOI not found (404)"}
            if code == 429 or code >= 500:
                last_err = f"HTTP {code}"  # transient: retry
            else:
                return False, {"error": f"HTTP {code}"}
        except error.URLError as e:
            last_err = f"URL error: {e.reason}"
        except (TimeoutError, OSError) as e:
            last_err = f"{str(e)[:120]}"

        if attempt < retries - 1:
            time.sleep(2 ** attempt)

    return False, {
        "error": f"network error after {retries} attempts ({last_err})",
        "network_error": True,
    }


def verify_url(url: str) -> Tuple[bool, str]:
    """
    Check URL accessibility with a HEAD request (compatibility helper only).

    The full citation verifier deliberately does not call this helper because
    reachability cannot establish bibliographic identity.

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
        code = e.code
        e.close()
        # Some servers reject HEAD but the resource exists; 403/405 are ambiguous
        if code in (403, 405):
            return True, f"HTTP {code} (HEAD rejected, resource likely exists)"
        return False, f"HTTP {code}"
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


def venue_similarity(v1: str, v2: str) -> float:
    """Compare venues without letting generic stopwords imply agreement."""
    stopwords = {"a", "an", "and", "for", "in", "of", "on", "the"}

    def without_stopwords(value: str) -> str:
        words = re.findall(r"\w+", value.casefold())
        return " ".join(word for word in words if word not in stopwords)

    return title_similarity(without_stopwords(v1), without_stopwords(v2))


# ---------------------------------------------------------------------------
# Crossref Lookup (primary — 50 req/sec, no API key needed)
# ---------------------------------------------------------------------------

def _best_title_match(
    candidates: List[Any], clean_title: str, title_key: str = "title"
) -> Tuple[Optional[Dict], float]:
    """Find the candidate with the highest title similarity. Returns (item, similarity)."""
    best_sim = 0.0
    best_item = None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        raw = item.get(title_key, "")
        if isinstance(raw, list):
            raw = raw[0] if raw and isinstance(raw[0], str) else ""
        elif not isinstance(raw, str):
            raw = ""
        if not raw.strip():
            continue
        sim = title_similarity(clean_title, raw)
        if sim > best_sim:
            best_sim = sim
            best_item = item
    return best_item, best_sim


def _optional_metadata_string(value: Any) -> str:
    """Normalize an optional string or one-element string list."""
    if isinstance(value, str):
        return value.strip()
    if (
        isinstance(value, (list, tuple))
        and len(value) == 1
        and isinstance(value[0], str)
    ):
        return value[0].strip()
    return ""


CROSSREF_API_BASE = "https://api.crossref.org/works"


def _http_get_json(url: str, headers: Optional[Dict[str, str]] = None,
                   retries: int = 3,
                   errors: Optional[List[str]] = None) -> Optional[Any]:
    """
    Generic HTTP GET returning parsed JSON.

    Retries with backoff on transient failures (HTTP 429/5xx, URLError,
    timeout). Non-transient HTTP errors and JSON decode failures are not
    retried; if an `errors` list is provided, failures are appended to it
    instead of being silently swallowed.
    """
    def _note(msg: str) -> None:
        if errors is not None:
            errors.append(msg)

    endpoint = url.split("?")[0]
    last_err = "unknown error"

    for attempt in range(retries):
        req = request.Request(url)
        req.add_header("User-Agent", _user_agent())
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        try:
            with request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8")
            try:
                return json.loads(raw)
            except json.JSONDecodeError as e:
                _note(f"JSON decode error from {endpoint}: {str(e)[:80]}")
                return None
        except error.HTTPError as e:
            code = e.code
            e.close()
            if code == 429 or code >= 500:
                last_err = f"HTTP {code}"  # transient: retry
            else:
                _note(f"HTTP {code} from {endpoint}")
                return None
        except error.URLError as e:
            last_err = f"URL error: {e.reason}"
        except (TimeoutError, OSError) as e:
            last_err = f"{str(e)[:120]}"

        if attempt < retries - 1:
            time.sleep(3 * (attempt + 1))

    _note(f"network error after {retries} attempts from {endpoint} ({last_err})")
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
    if not isinstance(data, dict):
        return False, {"error": "invalid Crossref response: expected object"}
    message = data.get("message")
    if not isinstance(message, dict):
        return False, {"error": "invalid Crossref response: message is not an object"}
    items = message.get("items")
    if not isinstance(items, list):
        return False, {"error": "invalid Crossref response: items is not a list"}
    if not items:
        return False, {"error": "no results from Crossref"}

    best_item, best_sim = _best_title_match(items, clean)
    if best_item is None or best_sim < 0.5:
        return False, {"error": f"no good title match (best similarity: {best_sim:.1%})"}

    # Extract authors
    authors = []
    raw_authors = best_item.get("author", [])
    if isinstance(raw_authors, list):
        for author in raw_authors:
            if not isinstance(author, dict):
                continue
            given = author.get("given", "")
            family = author.get("family", "")
            given = given.strip() if isinstance(given, str) else ""
            family = family.strip() if isinstance(family, str) else ""
            name = f"{given} {family}".strip()
            if name:
                authors.append(name)

    # Extract year from published-print or published-online
    year = None
    for date_field in ("published-print", "published-online"):
        date_value = best_item.get(date_field)
        if not isinstance(date_value, dict):
            continue
        date_parts = date_value.get("date-parts")
        if (
            isinstance(date_parts, list)
            and date_parts
            and isinstance(date_parts[0], list)
            and date_parts[0]
        ):
            year = date_parts[0][0]
            break

    # Extract venue
    venue = _optional_metadata_string(best_item.get("container-title", ""))
    title_value = _optional_metadata_string(best_item.get("title", ""))
    doi_value = best_item.get("DOI", "")
    doi = doi_value.strip() if isinstance(doi_value, str) else ""
    metadata = {
        "title": title_value,
        "authors": authors,
        "year": year,
        "venue": venue,
        "doi": doi,
        "source": "crossref",
        "title_similarity": best_sim,
    }
    gaps = BibtexCitationVerifier._metadata_identity_gaps(metadata)
    if gaps:
        metadata["error"] = (
            "incomplete Crossref metadata: missing or unusable "
            + ", ".join(gaps)
        )
        return False, metadata
    return True, metadata


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
    if not isinstance(data, dict):
        return False, {"error": "invalid Semantic Scholar response: expected object"}
    papers = data.get("data")
    if not isinstance(papers, list):
        return False, {"error": "invalid Semantic Scholar response: data is not a list"}
    if not papers:
        return False, {"error": "no results from Semantic Scholar"}

    best_paper, best_sim = _best_title_match(papers, clean)
    if best_paper is None or best_sim < 0.5:
        return False, {"error": f"no good title match (best similarity: {best_sim:.1%})"}

    authors = []
    raw_authors = best_paper.get("authors", [])
    if isinstance(raw_authors, list):
        for author in raw_authors:
            if not isinstance(author, dict):
                continue
            name = author.get("name", "")
            if isinstance(name, str) and name.strip():
                authors.append(name.strip())
    external_ids = best_paper.get("externalIds", {})
    if not isinstance(external_ids, dict):
        external_ids = {}
    doi_value = external_ids.get("DOI", "")
    doi = doi_value.strip() if isinstance(doi_value, str) else ""
    metadata = {
        "title": _optional_metadata_string(best_paper.get("title", "")),
        "authors": authors,
        "year": best_paper.get("year"),
        "venue": _optional_metadata_string(best_paper.get("venue", "")),
        "doi": doi,
        "source": "s2",
        "title_similarity": best_sim,
    }
    gaps = BibtexCitationVerifier._metadata_identity_gaps(metadata)
    if gaps:
        metadata["error"] = (
            "incomplete Semantic Scholar metadata: missing or unusable "
            + ", ".join(gaps)
        )
        return False, metadata
    return True, metadata


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


_LATEX_ACCENT_RE = re.compile(
    r"\{?\\(?:['\"`~^=.cuvHtdb])\s*\{?([A-Za-z])\}?\}?"
)


def _strip_diacritics(s: str) -> str:
    """Remove Unicode diacritics: ü→u, ç→c, ö→o, etc."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _clean_author_name(name: str) -> str:
    """Normalize LaTeX/Unicode accents and case symmetrically for name matching."""
    clean = name
    # Accent commands may be braced ({\"a}) or unbraced (\"a).
    previous = None
    while clean != previous:
        previous = clean
        clean = _LATEX_ACCENT_RE.sub(r"\1", clean)
        clean = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", clean)
    clean = re.sub(r"[{}]", "", clean)
    clean = _strip_diacritics(clean).casefold()
    return re.sub(r"\s+", " ", clean).strip()


def _normalized_last_name(name: str) -> str:
    """Extract the final family token from either BibTeX or API name order.

    Comparing the final token is conservative but handles particles
    symmetrically (``van Rossum, Guido`` and ``Guido van Rossum``).
    """
    clean = _clean_author_name(name)
    if not clean:
        return ""
    if "," in clean:
        family = clean.split(",", 1)[0].strip()
        family_words = family.split()
        return family_words[-1] if family_words else ""
    words = clean.split()
    return words[-1] if words else ""


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
        last = _normalized_last_name(part)
        if last:
            last_names.append(last)
    return last_names


def parse_s2_authors(s2_authors: List[str]) -> List[str]:
    """Extract normalized family names from external API author name lists."""
    last_names = []
    for name in s2_authors:
        last = _normalized_last_name(name)
        if last:
            last_names.append(last)
    return last_names


def author_similarity(bib_author: str, s2_authors: List[str]) -> Tuple[float, List[str]]:
    """
    Compare a BibTeX author string against an external metadata author list.

    Returns (similarity_score, list_of_mismatches).
    Similarity is Jaccard on last-name sets.
    """
    bib_lasts = set(parse_bib_authors(bib_author))
    s2_lasts = set(parse_s2_authors(s2_authors))

    if not bib_lasts and not s2_lasts:
        return 1.0, []
    if not bib_lasts or not s2_lasts:
        return 0.0, [f"bib={list(bib_lasts)}, metadata={list(s2_lasts)}"]

    intersection = bib_lasts & s2_lasts
    union = bib_lasts | s2_lasts
    sim = len(intersection) / len(union) if union else 0.0

    mismatches = []
    only_bib = bib_lasts - s2_lasts
    only_s2 = s2_lasts - bib_lasts
    if only_bib:
        mismatches.append(f"in bib only: {sorted(only_bib)}")
    if only_s2:
        mismatches.append(f"in metadata only: {sorted(only_s2)}")

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
CURRENT_YEAR = datetime.date.today().year


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

    return issues


# ---------------------------------------------------------------------------
# On-Disk Verification Cache
# ---------------------------------------------------------------------------

class VerificationCache:
    """
    Optional JSON cache (--cache PATH) keyed by DOI or normalized title,
    so re-runs skip already-verified entries. Corrupt cache files are
    ignored and rebuilt.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: Dict[str, Any] = {}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data = loaded
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                self.data = {}

    def get(self, key: str) -> Optional[Any]:
        return self.data.get(key)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            print(f"WARNING: Could not save cache: {e}", file=sys.stderr)


def normalize_title_key(title: str) -> str:
    """Normalize a title into a stable cache key."""
    clean = _clean_latex_title(title).lower()
    return re.sub(r"[^\w]+", " ", clean).strip()


DOI_CACHE_PREFIX = "doi-v2:"
EXTERNAL_CACHE_PREFIX = "title-v2:"


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
        4. For each .bib entry: hallucination patterns and metadata agreement
        5. Produce a verification report
    """

    # Status constants
    VERIFIED = "VERIFIED"
    EXT_VERIFIED = "EXT_VERIFIED"
    URL_VERIFIED = "URL_VERIFIED"
    SUSPICIOUS = "SUSPICIOUS"
    UNVERIFIED = "UNVERIFIED"

    # Issues containing these markers are "soft": they do not, by themselves,
    # override otherwise-valid identity evidence.
    SOFT_ISSUE_MARKERS = (
        "network error",
        "metadata incomplete",
    )

    TITLE_SIMILARITY_THRESHOLD = 0.5
    AUTHOR_SIMILARITY_THRESHOLD = 0.5
    VENUE_SIMILARITY_THRESHOLD = 0.3

    def __init__(
        self,
        bib_path: Path,
        tex_dir: Path,
        strict: bool = False,
        output_path: Optional[Path] = None,
        enable_s2: bool = True,
        s2_api_key: Optional[str] = None,
        cache_path: Optional[Path] = None,
    ):
        self.bib_path = bib_path
        self.tex_dir = tex_dir
        self.strict = strict
        self.output_path = output_path
        self.enable_s2 = enable_s2
        self.s2_api_key = s2_api_key
        self.cache: Optional[VerificationCache] = (
            VerificationCache(cache_path) if cache_path else None
        )

        # Will be populated during verification
        self.entries: Dict[str, Dict[str, str]] = {}
        self.cited_keys: Set[str] = set()
        self.key_to_files: Dict[str, List[str]] = {}
        self.results: Dict[str, Dict] = {}  # key -> verification result
        self.missing_keys: Set[str] = set()  # cited but not in .bib
        self.orphan_keys: Set[str] = set()   # in .bib but not cited
        self.suspicious_count: int = 0
        self.scan_errors: List[str] = []

        self._report_lines: List[str] = []

    # ---- Output helpers ----

    def _out(self, line: str = "") -> None:
        """Print and buffer a line for the report."""
        print(line)
        self._report_lines.append(line)

    def _separator(self, char: str = "=", width: int = 70) -> None:
        self._out(char * width)

    # ---- Status computation ----

    @classmethod
    def _is_soft_issue(cls, issue: str) -> bool:
        folded = issue.casefold()
        return any(marker.casefold() in folded for marker in cls.SOFT_ISSUE_MARKERS)

    @classmethod
    def compute_entry_status(cls, result: Dict) -> str:
        """
        Compute the final status for one entry from explicit booleans.
        Priority: mismatch / fabricated DOI > hard issues > identity evidence.

        URL accessibility is deliberately ignored: it cannot establish
        bibliographic identity.
        """
        if result.get("mismatch") or result.get("doi_not_found"):
            return cls.SUSPICIOUS
        hard_issues = [i for i in result.get("issues", [])
                       if not cls._is_soft_issue(i)]
        if hard_issues:
            return cls.SUSPICIOUS
        if result.get("doi_verified"):
            return cls.VERIFIED
        if result.get("ext_verified"):
            return cls.EXT_VERIFIED
        return cls.UNVERIFIED

    @staticmethod
    def _usable_metadata_authors(metadata: Dict) -> List[str]:
        """Return source author names that contain a usable family name."""
        authors = metadata.get("authors", [])
        if not isinstance(authors, (list, tuple)):
            return []
        return [
            author.strip()
            for author in authors
            if isinstance(author, str) and _normalized_last_name(author)
        ]

    @staticmethod
    def _validated_metadata_year(metadata: Dict) -> Optional[int]:
        """Return a plausible source year without coercing booleans or floats.

        Accepted forms are non-boolean integers and digit-only strings in the
        inclusive range 1000 through the current calendar year.
        """
        year = metadata.get("year")
        if isinstance(year, bool):
            return None
        if isinstance(year, int):
            value = year
        elif isinstance(year, str) and year.isascii() and year.isdigit():
            value = int(year)
        else:
            return None
        return value if 1000 <= value <= CURRENT_YEAR else None

    @classmethod
    def _has_usable_metadata_year(cls, metadata: Dict) -> bool:
        """Return whether source metadata supplies a validated publication year."""
        return cls._validated_metadata_year(metadata) is not None

    @staticmethod
    def _usable_metadata_venue(metadata: Dict) -> str:
        """Normalize an optional venue string; invalid shapes are inconclusive."""
        return _optional_metadata_string(metadata.get("venue", ""))

    @classmethod
    def _metadata_identity_gaps(cls, metadata: Dict) -> List[str]:
        """List required identity fields absent or unusable in source metadata."""
        gaps: List[str] = []
        title = metadata.get("title")
        if not isinstance(title, str) or not title.strip():
            gaps.append("title")
        if not cls._usable_metadata_authors(metadata):
            gaps.append("authors")
        if not cls._has_usable_metadata_year(metadata):
            gaps.append("year")
        return gaps

    @classmethod
    def _valid_doi_cache_record(cls, record: Any) -> bool:
        """Validate a DOI cache record before indexing or trusting it."""
        if not isinstance(record, dict):
            return False
        success = record.get("success")
        metadata = record.get("metadata")
        if not isinstance(success, bool) or not isinstance(metadata, dict):
            return False
        return not success or not cls._metadata_identity_gaps(metadata)

    @classmethod
    def _valid_external_cache_record(cls, record: Any) -> bool:
        """Validate an external-search cache record before indexing it."""
        if not isinstance(record, dict):
            return False
        found = record.get("found")
        metadata = record.get("metadata")
        if not isinstance(found, bool) or not isinstance(metadata, dict):
            return False
        return not found or not cls._metadata_identity_gaps(metadata)

    def _record_incomplete_metadata(
        self, source_label: str, gaps: List[str], result: Dict
    ) -> None:
        issue = (
            f"{source_label} metadata incomplete "
            f"(missing or unusable {', '.join(gaps)}); "
            "not used as verification evidence"
        )
        result["issues"].append(issue)
        self._out(f"    [i] {issue}")

    def _compare_metadata(
        self,
        fields: Dict[str, str],
        metadata: Dict,
        source_label: str,
        result: Dict,
    ) -> None:
        """Compare identity-bearing metadata using one conservative policy."""
        bib_title = fields.get("title", "")
        metadata_title = metadata.get("title", "")
        if bib_title and isinstance(metadata_title, str) and metadata_title.strip():
            sim = title_similarity(bib_title, metadata_title)
            self._out(f"    {source_label} title similarity: {sim:.1%}")
            if sim < self.TITLE_SIMILARITY_THRESHOLD:
                issue = (
                    f"Title mismatch ({source_label}): similarity {sim:.1%} "
                    f"(metadata title: '{str(metadata_title)[:60]}...')"
                )
                result["issues"].append(issue)
                result["mismatch"] = True
                self._out(f"    [!] {issue}")

        bib_author = fields.get("author", "")
        metadata_authors = self._usable_metadata_authors(metadata)
        if bib_author and metadata_authors:
            auth_sim, auth_mismatches = author_similarity(
                bib_author, metadata_authors
            )
            self._out(f"    {source_label} authors: similarity {auth_sim:.0%}")
            if auth_sim < self.AUTHOR_SIMILARITY_THRESHOLD:
                issue = (
                    f"Author mismatch ({source_label}): "
                    f"{'; '.join(auth_mismatches)}"
                )
                result["issues"].append(issue)
                result["mismatch"] = True
                self._out(f"    [!] {issue}")

        bib_year = fields.get("year", "")
        metadata_year = self._validated_metadata_year(metadata)
        if bib_year and metadata_year is not None:
            try:
                years_match = int(bib_year) == metadata_year
            except (ValueError, TypeError):
                years_match = True  # structural validation reports malformed years
            if not years_match:
                issue = (
                    f"Year mismatch ({source_label}): "
                    f"bib={bib_year}, {source_label}={metadata_year}"
                )
                result["issues"].append(issue)
                result["mismatch"] = True
                self._out(f"    [!] {issue}")

        # Some APIs omit a container title. Absence is inconclusive; a
        # contradiction is suspicious only when both sides provide a venue.
        bib_venue = fields.get("booktitle", "") or fields.get("journal", "")
        metadata_venue = self._usable_metadata_venue(metadata)
        if bib_venue and metadata_venue:
            venue_sim = venue_similarity(bib_venue, metadata_venue)
            self._out(
                f"    {source_label} venue: \"{metadata_venue}\" "
                f"(similarity: {venue_sim:.0%})"
            )
            if venue_sim < self.VENUE_SIMILARITY_THRESHOLD:
                issue = (
                    f"Venue mismatch ({source_label}): "
                    f"bib=\"{bib_venue[:50]}\", "
                    f"{source_label}=\"{str(metadata_venue)[:50]}\""
                )
                result["issues"].append(issue)
                result["mismatch"] = True
                self._out(f"    [!] {issue}")

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

        # Persist the cache if one is configured
        if self.cache:
            self.cache.save()

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

        parse_warnings: List[str] = []
        self.entries = parse_bibtex(bib_text, warnings=parse_warnings)
        self._out(f"      Found {len(self.entries)} entries")
        for w in parse_warnings:
            self._out(f"      [!] {w}")

        # List them
        for key, fields in self.entries.items():
            etype = fields.get("_type", "?")
            title = fields.get("title", "(no title)")[:70]
            self._out(f"        @{etype}{{{key}}} -- {title}")
        self._out()

    def _step_scan_tex(self) -> None:
        self._out("[2/5] Scanning .tex files for citations")
        self._out(f"      {self.tex_dir}")

        self.cited_keys, self.key_to_files, self.scan_errors = scan_tex_citations(
            self.tex_dir
        )
        self._out(f"      Found {len(self.cited_keys)} unique citation keys")
        for w in self.scan_errors:
            self._out(f"      [!] {w}")

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
                "url_present": bool(fields.get("url", "")),
                "ext_verified": False,
                "mismatch": False,        # metadata mismatch (title/author/year/venue)
                "doi_not_found": False,   # DOI resolved to 404 (likely fabricated)
                "network_error": False,   # transient network failure (retryable)
                "doi_metadata": {},
                "ext_metadata": {},
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

                # v2 invalidates records whose DOI authors were cached in the
                # old Family Given order.
                cache_key = f"{DOI_CACHE_PREFIX}{doi}"
                cached = self.cache.get(cache_key) if self.cache else None
                if self._valid_doi_cache_record(cached):
                    success, metadata = cached["success"], cached["metadata"]
                    self._out(f"    (from cache)")
                else:
                    if cached is not None:
                        self._out("    (ignored invalid or incomplete cache record)")
                    success, metadata = verify_doi(doi)
                    time.sleep(0.5)  # rate limit
                    # Cache complete successes and definitive failures only.
                    cacheable_success = (
                        success and not self._metadata_identity_gaps(metadata)
                    )
                    cacheable_failure = (
                        not success and not metadata.get("network_error")
                    )
                    if self.cache and (cacheable_success or cacheable_failure):
                        self.cache.set(cache_key,
                                       {"success": success, "metadata": metadata})

                if success:
                    result["doi_metadata"] = metadata
                    self._out("    DOI metadata received")
                    self._compare_metadata(fields, metadata, "DOI", result)
                    identity_gaps = self._metadata_identity_gaps(metadata)
                    if identity_gaps:
                        self._record_incomplete_metadata(
                            "DOI", identity_gaps, result
                        )
                    elif not result["mismatch"]:
                        result["doi_verified"] = True
                else:
                    err = metadata.get("error", "unknown error")
                    if metadata.get("network_error"):
                        result["network_error"] = True
                    elif "404" in err:
                        result["doi_not_found"] = True
                    result["issues"].append(f"DOI resolution failed: {err}")
                    self._out(f"    [X] DOI resolution failed: {err}")
            else:
                self._out(f"    DOI   : (none)")

            # 4c. Report URL presence without fetching arbitrary BibTeX URLs.
            url = fields.get("url", "")
            if url:
                self._out(f"    URL   : {url}")
                self._out("    URL   : present (informational; not fetched)")
            else:
                self._out(f"    URL   : (none)")

            # 4d. External API cross-verification (Crossref primary, S2 fallback)
            # Skip if DOI already verified cleanly — no need to burn API calls
            doi_clean = result["doi_verified"] and not result["mismatch"]
            if title and not doi_clean:
                self._out(f"    API   : Searching Crossref ...")
                ext_cache_key = f"{EXTERNAL_CACHE_PREFIX}{normalize_title_key(title)}"
                cached = self.cache.get(ext_cache_key) if self.cache else None
                if self._valid_external_cache_record(cached):
                    found, ext_meta = cached["found"], cached["metadata"]
                    self._out(f"    (from cache)")
                else:
                    if cached is not None:
                        self._out("    (ignored invalid or incomplete cache record)")
                    found, ext_meta = search_external(
                        title, enable_s2=self.enable_s2, s2_api_key=self.s2_api_key,
                        bib_author=fields.get("author", ""),
                    )
                    if (
                        self.cache
                        and found
                        and not self._metadata_identity_gaps(ext_meta)
                    ):
                        self.cache.set(ext_cache_key,
                                       {"found": found, "metadata": ext_meta})
                src = ext_meta.get("source", "?")
                src_label = "Crossref" if src == "crossref" else "S2"

                if found:
                    result["ext_metadata"] = ext_meta
                    sim_pct = ext_meta.get("title_similarity", 0)
                    self._out(f"    {src_label:8s}: Match found (title similarity: {sim_pct:.0%})")
                    self._out(f"    {src_label:8s}: \"{ext_meta.get('title', '')[:70]}\"")

                    self._compare_metadata(fields, ext_meta, src_label, result)

                    identity_gaps = self._metadata_identity_gaps(ext_meta)
                    if identity_gaps:
                        self._record_incomplete_metadata(
                            src_label, identity_gaps, result
                        )
                    elif not result["mismatch"]:
                        result["ext_verified"] = True
                else:
                    err = ext_meta.get("error", "unknown")
                    self._out(f"    API   : {err}")

            # 4e. Determine final status (single source of truth)
            ext_src = result.get("ext_metadata", {}).get("source", "s2")
            ext_label = "Crossref" if ext_src == "crossref" else "Semantic Scholar"

            result["status"] = self.compute_entry_status(result)

            status_display = {
                self.VERIFIED: "VERIFIED (DOI metadata agreement)",
                self.EXT_VERIFIED: f"VERIFIED ({ext_label} metadata agreement)",
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
        ext_verified = [k for k, r in self.results.items() if r["status"] == self.EXT_VERIFIED]
        suspicious = [k for k, r in self.results.items() if r["status"] == self.SUSPICIOUS]
        # Treat the retired URL_VERIFIED status as unverified if an old caller
        # injects it; URL reachability is never identity evidence.
        unverified = [
            k for k, r in self.results.items()
            if r["status"] in (self.UNVERIFIED, self.URL_VERIFIED)
        ]
        url_present_count = sum(
            1 for r in self.results.values() if r.get("url_present")
        )
        self.suspicious_count = len(suspicious)

        # Count by source for ext-verified
        cr_count = sum(1 for k in ext_verified
                       if self.results[k].get("ext_metadata", {}).get("source") == "crossref")
        s2_count = len(ext_verified) - cr_count

        total = len(self.results)
        self._out(f"  Total .bib entries   : {total}")
        self._out(f"  DOI metadata match   : {len(verified)}")
        self._out(f"  Crossref metadata    : {cr_count}")
        self._out(f"  S2 metadata          : {s2_count}")
        self._out(f"  URL present (info)   : {url_present_count}")
        self._out(f"  Suspicious           : {len(suspicious)}")
        self._out(f"  Unverified           : {len(unverified)}")
        self._out(f"  .tex read errors     : {len(self.scan_errors)}")
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
                self._out(
                    f"  {k}: {issues[0] if issues else 'no agreeing DOI/Crossref/S2 metadata'}"
                )
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

        if self.scan_errors:
            reasons.append(
                f"{len(self.scan_errors)} .tex file(s) could not be read; "
                "citation scan is incomplete"
            )
            failed = True

        if suspicious:
            reasons.append(f"{len(suspicious)} suspicious entry/entries detected")
            if self.strict:
                failed = True

        if unverified and self.strict:
            reasons.append(f"{len(unverified)} unverified entry/entries (strict mode)")
            failed = True

        total_ok = len(verified) + len(ext_verified)
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
            self._out(
                f"  {total_ok}/{total} entries verified by bibliographic "
                "metadata agreement"
            )

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

def compute_exit_code(passed: bool, suspicious_count: int) -> int:
    """
    Map verification outcome to a process exit code.

    0 = passed and no suspicious entries
    1 = failed (missing keys; strict-mode suspicious/unverified entries)
    2 = passed, but suspicious entries present (non-strict mode) — lets the
        Phase 7 gate detect metadata mismatches without strict mode.
    """
    if not passed:
        return 1
    if suspicious_count > 0:
        return 2
    return 0


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
  - DOI metadata agreement (required title/authors/year; venue when available)
  - Crossref / Semantic Scholar agreement under the same identity requirements
  - Report URL presence without fetching arbitrary BibTeX URLs
  - Hallucination pattern detection (generic titles, future years,
    anachronistic terms, missing fields, unverifiable entries)

Exit codes:
  0 = passed, no suspicious entries (possibly with warnings)
  1 = failed (missing keys, suspicious/unverified entries in strict mode, etc.)
  2 = passed, but suspicious entries present (non-strict mode)

Environment variables:
  CROSSREF_MAILTO  contact email for the Crossref polite pool (see --mailto)
  S2_API_KEY       Semantic Scholar API key (alternative to --s2-key)

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
        help="Semantic Scholar API key (optional, relaxes rate limits; "
             "the S2_API_KEY env var is used when this flag is absent)",
    )
    parser.add_argument(
        "--mailto",
        type=str,
        default=None,
        help="Contact email for the Crossref polite pool (also settable via "
             "the CROSSREF_MAILTO env var; omitted from requests if unset)",
    )
    parser.add_argument(
        "--cache",
        type=str,
        default=None,
        help="Path to an on-disk JSON cache (keyed by DOI / normalized title) "
             "so re-runs skip already-verified entries",
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

    set_mailto(args.mailto)

    verifier = BibtexCitationVerifier(
        bib_path=bib_path,
        tex_dir=tex_dir,
        strict=args.strict,
        output_path=output_path,
        enable_s2=not args.no_s2,
        s2_api_key=resolve_s2_key(args.s2_key),
        cache_path=Path(args.cache) if args.cache else None,
    )

    passed = verifier.run()
    sys.exit(compute_exit_code(passed, verifier.suspicious_count))


if __name__ == "__main__":
    main()
