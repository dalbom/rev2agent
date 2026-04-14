#!/usr/bin/env python3
"""
Academic Source Credibility Evaluator

Evaluates source credibility for academic research across four dimensions:
  - Domain authority (35%)
  - Recency (20%)
  - Expertise (25%)
  - Bias / neutrality (20%)

Usable as both a CLI tool and an importable module.

CLI examples:
    python source_evaluator.py --url "https://arxiv.org/abs/2301.00001" \
        --title "Some Paper" --date 2025-01-15 --author "Dr. Jane Smith"

    python source_evaluator.py --batch sources.json --output scores.json

Module example:
    from source_evaluator import SourceEvaluator
    evaluator = SourceEvaluator()
    score = evaluator.evaluate_source(
        url="https://arxiv.org/abs/2301.00001",
        title="Some Paper",
        date="2025-01-15",
        author="Dr. Jane Smith",
    )
    print(score)

Dependencies: Python 3.8+ standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CredibilityScore:
    """Credibility assessment for a single source."""

    url: str
    title: str
    overall_score: float           # 0-100 weighted composite
    domain_authority: float        # 0-100
    recency: float                 # 0-100
    expertise: float               # 0-100
    bias_score: float              # 0-100 (higher = more neutral)
    factors: Dict[str, str] = field(default_factory=dict)
    recommendation: str = ""       # high_trust / moderate_trust / low_trust / verify

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BatchResult:
    """Aggregate result from evaluating multiple sources."""

    sources: List[CredibilityScore]
    statistics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sources": [s.to_dict() for s in self.sources],
            "statistics": self.statistics,
        }


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class SourceEvaluator:
    """Evaluates source credibility for academic research."""

    # ------------------------------------------------------------------
    # Domain classification
    # ------------------------------------------------------------------

    # Tier 1 -- Academic publishers and repositories (score >= 90)
    ACADEMIC_DOMAINS: set = {
        # Major publishers
        "nature.com",
        "science.org",
        "cell.com",
        "springer.com",
        "link.springer.com",
        "sciencedirect.com",
        "wiley.com",
        "onlinelibrary.wiley.com",
        "tandfonline.com",
        "sagepub.com",
        "cambridge.org",
        "academic.oup.com",
        "oup.com",
        "elsevier.com",

        # IEEE / ACM
        "ieee.org",
        "ieeexplore.ieee.org",
        "acm.org",
        "dl.acm.org",

        # Preprint servers
        "arxiv.org",
        "biorxiv.org",
        "medrxiv.org",
        "ssrn.com",

        # Open-access publishers
        "plos.org",
        "journals.plos.org",
        "frontiersin.org",
        "mdpi.com",
        "hindawi.com",

        # Conference proceedings / review venues
        "openreview.net",
        "aclanthology.org",
        "proceedings.mlr.press",          # PMLR / JMLR
        "jmlr.org",
        "proceedings.neurips.cc",
        "cvpr.thecvf.com",
        "thecvf.com",
        "ecva.net",                       # ECCV proceedings

        # Indexes & databases
        "pubmed.ncbi.nlm.nih.gov",
        "scholar.google.com",
        "semanticscholar.org",
        "dblp.org",
        "dblp.uni-trier.de",

        # Medical journals
        "nejm.org",
        "thelancet.com",
        "bmj.com",
        "jamanetwork.com",
    }

    # Tier 2 -- Government & intl. organizations (score ~85)
    GOVERNMENT_DOMAINS: set = {
        "nih.gov",
        "cdc.gov",
        "fda.gov",
        "nasa.gov",
        "nsf.gov",
        "energy.gov",
        "nist.gov",
        "who.int",
        "europa.eu",
        "un.org",
        "worldbank.org",
        "gov.uk",
    }

    # Tier 3 -- Technical documentation (score ~75)
    TECH_DOC_DOMAINS: set = {
        "docs.python.org",
        "docs.scipy.org",
        "numpy.org",
        "pytorch.org",
        "tensorflow.org",
        "scikit-learn.org",
        "developer.mozilla.org",
        "docs.microsoft.com",
        "learn.microsoft.com",
        "cloud.google.com",
        "aws.amazon.com",
        "kubernetes.io",
        "readthedocs.io",
        "readthedocs.org",
    }

    # Tier 4 -- Reputable news / industry (score ~60)
    NEWS_DOMAINS: set = {
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "economist.com",
        "scientificamerican.com",
        "quantamagazine.org",
        "technologyreview.com",
        "techcrunch.com",
        "theverge.com",
        "arstechnica.com",
        "wired.com",
        "forbes.com",
        "bloomberg.com",
        "nytimes.com",
        "washingtonpost.com",
    }

    # Tier 5 -- Blog / user-generated platforms (score ~40)
    BLOG_PLATFORMS: list = [
        "blogspot.com",
        "wordpress.com",
        "wix.com",
        "substack.com",
        "medium.com",
        "dev.to",
        "hashnode.dev",
        "tumblr.com",
        "weebly.com",
    ]

    # Community Q&A -- useful but not primary (score ~55)
    COMMUNITY_DOMAINS: set = {
        "stackoverflow.com",
        "stackexchange.com",
        "github.com",
        "reddit.com",
        "quora.com",
        "wikipedia.org",
    }

    # Educational institution TLDs
    ACADEMIC_TLDS: list = [".edu", ".ac.uk", ".ac.jp", ".edu.au", ".ac.in"]

    # ------------------------------------------------------------------
    # Sensational language markers (for bias detection)
    # ------------------------------------------------------------------
    SENSATIONAL_PHRASES: list = [
        "shocking",
        "unbelievable",
        "you won't believe",
        "mind-blowing",
        "game-changer",
        "revolutionary",
        "they don't want you to know",
        "secret",
        "exposed",
        "destroyed",
        "slam",
        "!!!",
    ]

    # ------------------------------------------------------------------
    # Publication type keywords (for expertise scoring)
    # ------------------------------------------------------------------
    PEER_REVIEW_SIGNALS: list = [
        "journal",
        "transactions on",
        "proceedings of",
        "conference on",
        "symposium on",
        "workshop on",
        "ieee",
        "acm",
        "neurips",
        "icml",
        "iclr",
        "cvpr",
        "iccv",
        "eccv",
        "aaai",
        "ijcai",
        "emnlp",
        "acl ",
        "naacl",
        "miccai",
        "isbi",
    ]

    PREPRINT_SIGNALS: list = [
        "arxiv",
        "preprint",
        "biorxiv",
        "medrxiv",
        "ssrn",
        "working paper",
        "technical report",
    ]

    CREDENTIAL_KEYWORDS: list = [
        "dr.",
        "dr ",
        "ph.d",
        "phd",
        "professor",
        "prof.",
        "prof ",
        "m.d.",
    ]

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_source(
        self,
        url: str,
        title: str = "",
        date: Optional[str] = None,
        author: Optional[str] = None,
        content: Optional[str] = None,
    ) -> CredibilityScore:
        """Evaluate a single source and return a CredibilityScore.

        Parameters
        ----------
        url : str
            Full URL of the source.
        title : str
            Title of the paper / article / page.
        date : str or None
            Publication date in any ISO-ish format (YYYY-MM-DD preferred).
        author : str or None
            Author name(s) or affiliation string.
        content : str or None
            Optional body text for deeper bias analysis.
        """
        domain = self._extract_domain(url)

        domain_score = self._score_domain_authority(domain, url)
        recency_score = self._score_recency(date)
        expertise_score = self._score_expertise(domain, url, title, author)
        bias_score = self._score_bias(domain, title, content)

        overall = (
            domain_score * 0.35
            + recency_score * 0.20
            + expertise_score * 0.25
            + bias_score * 0.20
        )

        factors = self._identify_factors(
            domain, domain_score, recency_score, expertise_score, bias_score
        )
        recommendation = self._recommendation(overall)

        return CredibilityScore(
            url=url,
            title=title,
            overall_score=round(overall, 2),
            domain_authority=round(domain_score, 2),
            recency=round(recency_score, 2),
            expertise=round(expertise_score, 2),
            bias_score=round(bias_score, 2),
            factors=factors,
            recommendation=recommendation,
        )

    def evaluate_batch(self, sources: List[Dict[str, Any]]) -> BatchResult:
        """Evaluate a list of sources and compute aggregate statistics.

        Each element of *sources* is a dict with keys accepted by
        ``evaluate_source`` (``url`` is required; others are optional).
        """
        scores: List[CredibilityScore] = []
        for src in sources:
            score = self.evaluate_source(
                url=src.get("url", ""),
                title=src.get("title", ""),
                date=src.get("date", None),
                author=src.get("author", None),
                content=src.get("content", None),
            )
            scores.append(score)

        statistics = self._compute_statistics(scores)
        return BatchResult(sources=scores, statistics=statistics)

    # ------------------------------------------------------------------
    # Domain authority (35 %)
    # ------------------------------------------------------------------

    def _score_domain_authority(self, domain: str, url: str) -> float:
        """Return 0-100 authority score based on the domain."""

        # Check exact match in academic tier
        if domain in self.ACADEMIC_DOMAINS:
            return 95.0

        # Check if any academic domain is a suffix (e.g. sub.nature.com)
        for ad in self.ACADEMIC_DOMAINS:
            if domain.endswith("." + ad):
                return 93.0

        # Academic institution TLDs (.edu, .ac.uk, etc.)
        for tld in self.ACADEMIC_TLDS:
            if domain.endswith(tld):
                return 90.0

        # Government / intergovernmental
        if domain in self.GOVERNMENT_DOMAINS:
            return 85.0
        if domain.endswith(".gov") or domain.endswith(".gov.uk"):
            return 85.0

        # Technical documentation
        if domain in self.TECH_DOC_DOMAINS:
            return 75.0
        for td in self.TECH_DOC_DOMAINS:
            if domain.endswith("." + td):
                return 73.0

        # Community Q&A
        if domain in self.COMMUNITY_DOMAINS:
            return 55.0

        # News / industry
        if domain in self.NEWS_DOMAINS:
            return 60.0

        # Blog platforms
        for bp in self.BLOG_PLATFORMS:
            if bp in domain:
                return 40.0

        # Fallback -- unknown domain
        return 55.0

    # ------------------------------------------------------------------
    # Recency (20 %)
    # ------------------------------------------------------------------

    def _score_recency(self, date_str: Optional[str]) -> float:
        """Return 0-100 recency score."""
        if not date_str:
            return 50.0

        pub_date = self._parse_date(date_str)
        if pub_date is None:
            return 50.0

        now = datetime.now()
        age = now - pub_date

        if age < timedelta(days=365):
            return 100.0
        elif age < timedelta(days=730):
            return 85.0
        elif age < timedelta(days=1825):
            return 70.0
        elif age < timedelta(days=3650):
            return 50.0
        else:
            return 30.0

    # ------------------------------------------------------------------
    # Expertise (25 %)
    # ------------------------------------------------------------------

    def _score_expertise(
        self,
        domain: str,
        url: str,
        title: str,
        author: Optional[str],
    ) -> float:
        """Return 0-100 expertise score."""
        score = 50.0
        title_lower = title.lower()
        url_lower = url.lower()

        # --- Publication type ---

        # Peer-reviewed venue signals
        is_peer_reviewed = any(
            kw in title_lower or kw in url_lower for kw in self.PEER_REVIEW_SIGNALS
        )
        if is_peer_reviewed:
            score += 30

        # Preprint (still academic, but slightly less weight than peer-reviewed)
        elif any(kw in title_lower or kw in url_lower for kw in self.PREPRINT_SIGNALS):
            score += 22

        # Academic domain in general (if not already caught above)
        elif domain in self.ACADEMIC_DOMAINS or any(
            domain.endswith(tld) for tld in self.ACADEMIC_TLDS
        ):
            score += 18

        # Government / official body
        elif domain in self.GOVERNMENT_DOMAINS or domain.endswith(".gov"):
            score += 20

        # Technical documentation
        elif domain in self.TECH_DOC_DOMAINS or "docs." in domain:
            score += 12

        # --- Author credentials ---
        if author:
            author_lower = author.lower()
            if any(cred in author_lower for cred in self.CREDENTIAL_KEYWORDS):
                score += 15
            # University affiliation heuristic
            if any(
                kw in author_lower
                for kw in ["university", "institute", "laboratory", "lab ", "dept"]
            ):
                score += 10

        return min(score, 100.0)

    # ------------------------------------------------------------------
    # Bias / neutrality (20 %)
    # ------------------------------------------------------------------

    def _score_bias(
        self,
        domain: str,
        title: str,
        content: Optional[str],
    ) -> float:
        """Return 0-100 neutrality score (higher = more neutral)."""
        score = 70.0
        title_lower = title.lower()

        # Academic / government sources are generally neutral
        if domain in self.ACADEMIC_DOMAINS or any(
            domain.endswith(tld) for tld in self.ACADEMIC_TLDS
        ):
            score += 20
        elif domain in self.GOVERNMENT_DOMAINS or domain.endswith(".gov"):
            score += 15

        # Sensational language in the title
        sensational_count = sum(
            1 for phrase in self.SENSATIONAL_PHRASES if phrase in title_lower
        )
        score -= sensational_count * 12

        # ALL-CAPS title (excluding acronyms of <= 5 chars)
        words = title.split()
        caps_words = [w for w in words if w.isupper() and len(w) > 5]
        if len(caps_words) > len(words) * 0.3 and len(words) > 3:
            score -= 15

        # Exclamation marks
        score -= title.count("!") * 5

        # Content analysis (optional)
        if content:
            content_lower = content.lower()
            # Balanced discourse markers
            balance_markers = [
                "however",
                "although",
                "on the other hand",
                "conversely",
                "in contrast",
                "limitation",
                "future work",
                "we acknowledge",
            ]
            balance_count = sum(1 for m in balance_markers if m in content_lower)
            score += min(balance_count * 4, 15)

            # Promotional / marketing language
            promo_markers = [
                "buy now",
                "subscribe",
                "discount",
                "limited time",
                "click here",
                "sign up",
            ]
            promo_count = sum(1 for m in promo_markers if m in content_lower)
            score -= promo_count * 8

        return max(min(score, 100.0), 0.0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_domain(url: str) -> str:
        """Return the bare domain from *url*, stripping 'www.' prefix."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    @staticmethod
    def _parse_date(date_str: str) -> Optional[datetime]:
        """Try several common date formats and return a datetime or None."""
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y/%m/%d",
            "%d %b %Y",       # 15 Jan 2025
            "%d %B %Y",       # 15 January 2025
            "%B %d, %Y",      # January 15, 2025
            "%b %d, %Y",      # Jan 15, 2025
            "%Y",             # Year only
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        # Last resort: try fromisoformat (Python 3.7+)
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def _identify_factors(
        self,
        domain: str,
        domain_score: float,
        recency_score: float,
        expertise_score: float,
        bias_score: float,
    ) -> Dict[str, str]:
        """Build a dict of human-readable factor notes."""
        factors: Dict[str, str] = {}

        if domain_score >= 90:
            factors["domain"] = "High-authority academic domain"
        elif domain_score >= 75:
            factors["domain"] = "Trusted technical/government domain"
        elif domain_score >= 55:
            factors["domain"] = "Moderate authority -- verify claims independently"
        else:
            factors["domain"] = "Low-authority domain -- treat with caution"

        if recency_score >= 85:
            factors["recency"] = "Recent publication (< 2 years)"
        elif recency_score >= 50:
            factors["recency"] = "Moderately dated (2-10 years)"
        elif recency_score > 0:
            factors["recency"] = "Outdated (> 10 years) -- check for newer work"
        else:
            factors["recency"] = "Publication date unknown"

        if expertise_score >= 80:
            factors["expertise"] = "Expert / peer-reviewed source"
        elif expertise_score >= 60:
            factors["expertise"] = "Credible source with some expertise indicators"
        else:
            factors["expertise"] = "Limited expertise signals -- verify author credentials"

        if bias_score >= 80:
            factors["bias"] = "Low bias -- balanced academic tone"
        elif bias_score >= 55:
            factors["bias"] = "Moderate neutrality"
        else:
            factors["bias"] = "Potential bias or sensationalism detected"

        return factors

    @staticmethod
    def _recommendation(overall: float) -> str:
        if overall >= 80:
            return "high_trust"
        elif overall >= 60:
            return "moderate_trust"
        elif overall >= 40:
            return "low_trust"
        else:
            return "verify"

    @staticmethod
    def _compute_statistics(scores: List[CredibilityScore]) -> Dict[str, Any]:
        """Compute aggregate statistics over a list of scores."""
        if not scores:
            return {
                "count": 0,
                "mean_overall": 0,
                "min_overall": 0,
                "max_overall": 0,
                "mean_domain_authority": 0,
                "mean_recency": 0,
                "mean_expertise": 0,
                "mean_bias": 0,
                "recommendation_counts": {},
            }

        n = len(scores)
        overalls = [s.overall_score for s in scores]
        rec_counts: Dict[str, int] = {}
        for s in scores:
            rec_counts[s.recommendation] = rec_counts.get(s.recommendation, 0) + 1

        return {
            "count": n,
            "mean_overall": round(sum(overalls) / n, 2),
            "min_overall": round(min(overalls), 2),
            "max_overall": round(max(overalls), 2),
            "mean_domain_authority": round(
                sum(s.domain_authority for s in scores) / n, 2
            ),
            "mean_recency": round(sum(s.recency for s in scores) / n, 2),
            "mean_expertise": round(sum(s.expertise for s in scores) / n, 2),
            "mean_bias": round(sum(s.bias_score for s in scores) / n, 2),
            "recommendation_counts": rec_counts,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate source credibility for academic research.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  %(prog)s --url "https://arxiv.org/abs/2301.00001" '
            '--title "Paper Title"\n'
            '  %(prog)s --url "https://arxiv.org/abs/2301.00001" '
            '--title "Paper Title" --date 2025-01-15 --author "Dr. Smith"\n'
            "  %(prog)s --batch sources.json --output scores.json\n"
        ),
    )
    # Single-source mode
    parser.add_argument("--url", type=str, help="URL of the source to evaluate")
    parser.add_argument("--title", type=str, default="", help="Title of the source")
    parser.add_argument("--date", type=str, default=None, help="Publication date (YYYY-MM-DD)")
    parser.add_argument("--author", type=str, default=None, help="Author name(s)")

    # Batch mode
    parser.add_argument(
        "--batch",
        type=str,
        default=None,
        metavar="FILE",
        help="Path to a JSON file with a list of sources to evaluate",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="FILE",
        help="Write JSON results to FILE instead of stdout",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    evaluator = SourceEvaluator()

    # ---- Batch mode ----
    if args.batch:
        with open(args.batch, "r", encoding="utf-8") as f:
            sources = json.load(f)

        if not isinstance(sources, list):
            print("Error: batch JSON must be a list of source objects.", file=sys.stderr)
            sys.exit(1)

        result = evaluator.evaluate_batch(sources)
        output_json = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_json + "\n")
            print(f"Results written to {args.output}")
        else:
            print(output_json)
        return

    # ---- Single-source mode ----
    if not args.url:
        parser.print_help()
        sys.exit(1)

    score = evaluator.evaluate_source(
        url=args.url,
        title=args.title,
        date=args.date,
        author=args.author,
    )

    output_json = json.dumps(score.to_dict(), indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_json + "\n")
        print(f"Results written to {args.output}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
