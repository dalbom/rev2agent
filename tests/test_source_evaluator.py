"""Tests for scripts/source_evaluator.py."""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import source_evaluator as se  # noqa: E402


class TestTimezoneAwareDates(unittest.TestCase):
    """Bug 16: tz-aware dates must not raise when compared to naive now()."""

    def test_parse_date_returns_naive(self):
        dt = se.SourceEvaluator._parse_date("2025-01-15T10:00:00+09:00")
        self.assertIsNotNone(dt)
        self.assertIsNone(dt.tzinfo)
        # 10:00 at +09:00 is 01:00 UTC
        self.assertEqual(dt.hour, 1)

    def test_evaluate_with_offset_date_does_not_raise(self):
        ev = se.SourceEvaluator()
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        score = ev.evaluate_source(
            url="https://arxiv.org/abs/2301.00001",
            title="Some Paper",
            date=recent,
        )
        self.assertEqual(score.recency, 100.0)

    def test_z_suffix_date(self):
        ev = se.SourceEvaluator()
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        score = ev.evaluate_source(
            url="https://arxiv.org/abs/2301.00001",
            title="Some Paper",
            date=recent,
        )
        self.assertEqual(score.recency, 100.0)


class TestPublicationDateAlias(unittest.TestCase):
    """Bug 17: publication_date accepted as alias for date."""

    def test_kwarg_alias(self):
        ev = se.SourceEvaluator()
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        score = ev.evaluate_source(
            url="https://arxiv.org/abs/2301.00001",
            title="Some Paper",
            publication_date=recent,
        )
        self.assertEqual(score.recency, 100.0)

    def test_date_wins_over_alias(self):
        ev = se.SourceEvaluator()
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        old = "1990-01-01"
        score = ev.evaluate_source(
            url="https://arxiv.org/abs/2301.00001",
            title="Some Paper",
            date=recent,
            publication_date=old,
        )
        self.assertEqual(score.recency, 100.0)

    def test_batch_alias(self):
        ev = se.SourceEvaluator()
        recent = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
        result = ev.evaluate_batch([{
            "url": "https://arxiv.org/abs/2301.00001",
            "title": "Some Paper",
            "publication_date": recent,
        }])
        self.assertEqual(result.sources[0].recency, 100.0)


class TestDomainFallback(unittest.TestCase):
    """Bug 18: unknown-domain fallback below community (55), above blogs (40)."""

    def test_unknown_domain_is_45(self):
        ev = se.SourceEvaluator()
        score = ev._score_domain_authority(
            "randomsite12345.xyz", "https://randomsite12345.xyz/post")
        self.assertEqual(score, 45.0)

    def test_ordering_community_above_unknown_above_blogs(self):
        ev = se.SourceEvaluator()
        community = ev._score_domain_authority(
            "stackoverflow.com", "https://stackoverflow.com/q/1")
        unknown = ev._score_domain_authority(
            "randomsite12345.xyz", "https://randomsite12345.xyz/")
        blog = ev._score_domain_authority(
            "someone.blogspot.com", "https://someone.blogspot.com/")
        self.assertGreater(community, unknown)
        self.assertGreater(unknown, blog)

    def test_batch_warns_on_missing_url(self):
        ev = se.SourceEvaluator()
        result = ev.evaluate_batch([{"title": "No URL here"}])
        self.assertTrue(result.warnings)
        self.assertTrue(any("url" in w.lower() for w in result.warnings))
        self.assertIn("warnings", result.to_dict())

    def test_batch_no_warning_for_good_url(self):
        ev = se.SourceEvaluator()
        result = ev.evaluate_batch([{
            "url": "https://arxiv.org/abs/2301.00001",
            "title": "Fine",
        }])
        self.assertEqual(result.warnings, [])


class TestHappyPath(unittest.TestCase):
    def test_arxiv_source(self):
        ev = se.SourceEvaluator()
        score = ev.evaluate_source(
            url="https://arxiv.org/abs/2301.00001",
            title="Deep Learning for Testing: NeurIPS Edition",
            date="2025-01-15",
            author="Dr. Jane Smith, Example University",
        )
        self.assertEqual(score.domain_authority, 95.0)
        self.assertGreaterEqual(score.overall_score, 80.0)
        self.assertEqual(score.recommendation, "high_trust")

    def test_batch_statistics(self):
        ev = se.SourceEvaluator()
        result = ev.evaluate_batch([
            {"url": "https://arxiv.org/abs/2301.00001", "title": "Paper A"},
            {"url": "https://example.org/blog", "title": "Blog B"},
        ])
        self.assertEqual(result.statistics["count"], 2)
        self.assertIn("mean_overall", result.statistics)


if __name__ == "__main__":
    unittest.main()
