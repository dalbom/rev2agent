"""Tests for scripts/verify_citations_bibtex.py (no network access)."""

import contextlib
import datetime
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib import error

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_citations_bibtex as vcb  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class FakeResponse:
    """Minimal stand-in for urlopen's response context manager."""

    def __init__(self, payload):
        self._payload = payload

    def read(self):
        if isinstance(self._payload, bytes):
            return self._payload
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def http_error(code):
    return error.HTTPError("https://example.org", code, f"HTTP {code}", None, None)


# ---------------------------------------------------------------------------
# Bug 1: \cite regex must handle optional [...] args and starred forms
# ---------------------------------------------------------------------------

class TestCiteRegex(unittest.TestCase):
    def _keys(self, tex):
        return [m.group(1) for m in vcb._CITE_RE.finditer(tex)]

    def test_plain_cite(self):
        self.assertEqual(self._keys(r"\cite{key1}"), ["key1"])

    def test_citep_with_two_optional_args(self):
        self.assertEqual(self._keys(r"\citep[e.g.][]{key1}"), ["key1"])

    def test_cite_with_postnote(self):
        self.assertEqual(self._keys(r"\cite[p.~3]{key2}"), ["key2"])

    def test_starred_citet(self):
        self.assertEqual(self._keys(r"\citet*{key3}"), ["key3"])

    def test_capitalized_cite(self):
        self.assertEqual(self._keys(r"\Citep{key4}"), ["key4"])

    def test_multi_key(self):
        self.assertEqual(self._keys(r"\citep[see][ch.~2]{a,b}"), ["a,b"])


# ---------------------------------------------------------------------------
# Bug 2: field parsing (deep brace nesting, macros, escaped quotes, dup keys)
# ---------------------------------------------------------------------------

class TestBibtexFieldParsing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (FIXTURES / "refs_nested.bib").read_text(encoding="utf-8")
        cls.warnings = []
        cls.entries = vcb.parse_bibtex(cls.text, warnings=cls.warnings)

    def test_four_level_brace_nesting_kept(self):
        self.assertIn("nested2024", self.entries)
        self.assertEqual(
            self.entries["nested2024"]["title"],
            "A {Nested {Brace {Level4}}} Title",
        )

    def test_fields_after_deep_title_survive(self):
        self.assertEqual(self.entries["nested2024"]["year"], "2024")
        self.assertEqual(self.entries["nested2024"]["doi"], "10.1234/test.5678")

    def test_string_macro_reference_warns(self):
        # journal = tpami is an unexpanded @string macro: warn, don't fail
        self.assertIn("macro2023", self.entries)
        self.assertTrue(
            any("macro" in w.lower() and "tpami" in w for w in self.warnings),
            f"expected macro warning, got: {self.warnings}",
        )
        # Year after the macro field must still be parsed
        self.assertEqual(self.entries["macro2023"]["year"], "2023")

    def test_escaped_quote_in_quoted_value(self):
        self.assertEqual(
            self.entries["quoted2022"]["title"],
            'An \\"Escaped\\" Quote Title',
        )
        self.assertEqual(self.entries["quoted2022"]["year"], "2022")

    def test_duplicate_keys_warn_and_keep_first(self):
        self.assertEqual(self.entries["dupkey2021"]["title"], "First Version")
        self.assertTrue(
            any("duplicate" in w.lower() for w in self.warnings),
            f"expected duplicate-key warning, got: {self.warnings}",
        )

    def test_bare_number_value(self):
        self.assertEqual(self.entries["quoted2022"]["year"], "2022")


# ---------------------------------------------------------------------------
# Bug 5: .tex scanning must strip comments and warn on unreadable files
# ---------------------------------------------------------------------------

class TestScanTexCitations(unittest.TestCase):
    def test_comments_stripped(self):
        cited, key_to_files, warnings = vcb.scan_tex_citations(FIXTURES / "tex")
        self.assertIn("nested2024", cited)
        self.assertIn("macro2023", cited)
        self.assertIn("quoted2022", cited)
        self.assertIn("plain2020", cited)
        self.assertIn("after_percent", cited)
        self.assertNotIn("commented_out", cited)
        self.assertNotIn("also_commented", cited)

    def test_unreadable_file_warns(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "good.tex").write_text(r"\cite{ok}", encoding="utf-8")
            # A directory named *.tex matches rglob but cannot be read
            (tdir / "bad.tex").mkdir()
            cited, _, warnings = vcb.scan_tex_citations(tdir)
            self.assertIn("ok", cited)
            self.assertTrue(
                any("bad.tex" in w for w in warnings),
                f"expected warning for unreadable bad.tex, got: {warnings}",
            )


# ---------------------------------------------------------------------------
# Bug 3: retry on transient network failures
# ---------------------------------------------------------------------------

class TestVerifyDoiRetry(unittest.TestCase):
    CSL = {
        "title": "A Paper",
        "issued": {"date-parts": [[2024]]},
        "author": [{"family": "Smith", "given": "John"}],
        "container-title": "Journal of Testing",
    }

    def test_retries_on_transient_then_succeeds(self):
        calls = []
        http_errors = []

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            if len(calls) == 1:
                raise error.URLError("connection reset")
            if len(calls) == 2:
                exc = http_error(503)
                http_errors.append(exc)
                raise exc
            return FakeResponse(self.CSL)

        with mock.patch.object(vcb.request, "urlopen", fake_urlopen), \
                mock.patch.object(vcb.time, "sleep"):
            ok, meta = vcb.verify_doi("10.1234/test.5678")
        self.assertTrue(ok)
        self.assertEqual(meta["title"], "A Paper")
        self.assertEqual(meta["authors"], ["John Smith"])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(exc.closed for exc in http_errors))

    def test_404_is_not_retried(self):
        calls = []
        exc = http_error(404)

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            raise exc

        with mock.patch.object(vcb.request, "urlopen", fake_urlopen), \
                mock.patch.object(vcb.time, "sleep"):
            ok, meta = vcb.verify_doi("10.1234/does.not.exist")
        self.assertFalse(ok)
        self.assertEqual(len(calls), 1)
        self.assertIn("404", meta["error"])
        self.assertFalse(meta.get("network_error", False))
        self.assertTrue(exc.closed)

    def test_nontransient_http_error_is_closed(self):
        exc = http_error(400)
        with mock.patch.object(vcb.request, "urlopen", side_effect=exc):
            ok, meta = vcb.verify_doi("10.1234/bad-request")
        self.assertFalse(ok)
        self.assertIn("400", meta["error"])
        self.assertTrue(exc.closed)

    def test_persistent_network_error_flagged(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            raise error.URLError("no route to host")

        with mock.patch.object(vcb.request, "urlopen", fake_urlopen), \
                mock.patch.object(vcb.time, "sleep"):
            ok, meta = vcb.verify_doi("10.1234/test.5678")
        self.assertFalse(ok)
        self.assertEqual(len(calls), 3)
        self.assertTrue(meta.get("network_error"))
        self.assertIn("network", meta["error"].lower())


class TestHttpGetJsonRetry(unittest.TestCase):
    def test_retries_on_5xx_then_succeeds(self):
        calls = []
        http_errors = []

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            if len(calls) < 3:
                exc = http_error(502)
                http_errors.append(exc)
                raise exc
            return FakeResponse({"ok": True})

        with mock.patch.object(vcb.request, "urlopen", fake_urlopen), \
                mock.patch.object(vcb.time, "sleep"):
            data = vcb._http_get_json("https://api.example.org/x")
        self.assertEqual(data, {"ok": True})
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(exc.closed for exc in http_errors))

    def test_nontransient_http_error_is_closed(self):
        exc = http_error(404)
        errors = []
        with mock.patch.object(vcb.request, "urlopen", side_effect=exc):
            data = vcb._http_get_json("https://api.example.org/missing", errors=errors)
        self.assertIsNone(data)
        self.assertTrue(any("404" in message for message in errors), errors)
        self.assertTrue(exc.closed)

    def test_retries_on_urlerror(self):
        calls = []

        def fake_urlopen(req, timeout=None):
            calls.append(req)
            if len(calls) == 1:
                raise error.URLError("timed out")
            return FakeResponse({"ok": 1})

        with mock.patch.object(vcb.request, "urlopen", fake_urlopen), \
                mock.patch.object(vcb.time, "sleep"):
            data = vcb._http_get_json("https://api.example.org/x")
        self.assertEqual(data, {"ok": 1})
        self.assertEqual(len(calls), 2)

    def test_json_decode_error_is_logged_not_swallowed(self):
        def fake_urlopen(req, timeout=None):
            return FakeResponse(b"this is not json")

        errors = []
        with mock.patch.object(vcb.request, "urlopen", fake_urlopen), \
                mock.patch.object(vcb.time, "sleep"):
            data = vcb._http_get_json("https://api.example.org/x", errors=errors)
        self.assertIsNone(data)
        self.assertTrue(any("json" in e.lower() for e in errors), errors)


class TestVerifyUrlLifecycle(unittest.TestCase):
    def test_http_error_is_closed_even_for_ambiguous_head_response(self):
        exc = http_error(405)
        with mock.patch.object(vcb.request, "urlopen", side_effect=exc):
            ok, message = vcb.verify_url("https://example.org/paper")
        self.assertTrue(ok)
        self.assertIn("405", message)
        self.assertTrue(exc.closed)

    def test_nontransient_http_error_is_closed(self):
        exc = http_error(404)
        with mock.patch.object(vcb.request, "urlopen", side_effect=exc):
            ok, message = vcb.verify_url("https://example.org/missing")
        self.assertFalse(ok)
        self.assertIn("404", message)
        self.assertTrue(exc.closed)


# ---------------------------------------------------------------------------
# Bug 6: explicit status computation
# ---------------------------------------------------------------------------

class TestStatusComputation(unittest.TestCase):
    def _result(self, **kw):
        base = {
            "doi_verified": False,
            "url_verified": False,
            "ext_verified": False,
            "mismatch": False,
            "doi_not_found": False,
            "issues": [],
        }
        base.update(kw)
        return base

    def test_mismatch_always_suspicious(self):
        r = self._result(doi_verified=True, mismatch=True)
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.SUSPICIOUS,
        )

    def test_doi_404_suspicious(self):
        r = self._result(ext_verified=True, doi_not_found=True)
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.SUSPICIOUS,
        )

    def test_doi_verified_with_transient_network_issue(self):
        r = self._result(doi_verified=True,
                         issues=["External lookup network error after 3 attempts"])
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.VERIFIED,
        )

    def test_ext_verified(self):
        r = self._result(ext_verified=True)
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.EXT_VERIFIED,
        )

    def test_url_only_is_unverified(self):
        r = self._result(url_verified=True)
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.UNVERIFIED,
        )

    def test_doi_evidence_does_not_override_missing_author(self):
        r = self._result(doi_verified=True, issues=["Missing author field"])
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.SUSPICIOUS,
        )

    def test_external_evidence_does_not_override_missing_year(self):
        r = self._result(ext_verified=True, issues=["Missing year field"])
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.SUSPICIOUS,
        )

    def test_unverified_with_hard_issue_is_suspicious(self):
        r = self._result(issues=["Suspicious title pattern: Generic academic title pattern"])
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.SUSPICIOUS,
        )

    def test_unverified_with_only_network_issue(self):
        r = self._result(issues=["DOI resolution failed: network error after 3 attempts"])
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.UNVERIFIED,
        )

    def test_clean_unverified(self):
        r = self._result()
        self.assertEqual(
            vcb.BibtexCitationVerifier.compute_entry_status(r),
            vcb.BibtexCitationVerifier.UNVERIFIED,
        )


# ---------------------------------------------------------------------------
# Bug 4: exit code semantics
# ---------------------------------------------------------------------------

class TestExitCode(unittest.TestCase):
    def test_failed_is_1(self):
        self.assertEqual(vcb.compute_exit_code(passed=False, suspicious_count=0), 1)
        self.assertEqual(vcb.compute_exit_code(passed=False, suspicious_count=3), 1)

    def test_suspicious_nonstrict_is_2(self):
        self.assertEqual(vcb.compute_exit_code(passed=True, suspicious_count=1), 2)

    def test_clean_is_0(self):
        self.assertEqual(vcb.compute_exit_code(passed=True, suspicious_count=0), 0)


# ---------------------------------------------------------------------------
# Bug 7: CURRENT_YEAR must not be hardcoded
# ---------------------------------------------------------------------------

class TestCurrentYear(unittest.TestCase):
    def test_current_year_from_clock(self):
        self.assertEqual(vcb.CURRENT_YEAR, datetime.date.today().year)

    def test_future_year_detection(self):
        entry = {
            "title": "Quantum Widget Optimization in Practice",
            "author": "Smith, John",
            "year": str(datetime.date.today().year + 1),
            "doi": "10.1/x",
        }
        issues = vcb.detect_hallucination_patterns(entry)
        self.assertTrue(any("Future year" in i for i in issues), issues)


# ---------------------------------------------------------------------------
# Bug 8: configurable Crossref mailto contact
# ---------------------------------------------------------------------------

class TestUserAgent(unittest.TestCase):
    def test_no_contact_omits_mailto(self):
        with mock.patch.dict(vcb.os.environ, {}, clear=True):
            vcb.set_mailto(None)
            self.assertNotIn("mailto", vcb._user_agent())
            self.assertNotIn("example.com", vcb._user_agent())

    def test_env_var_used(self):
        with mock.patch.dict(vcb.os.environ, {"CROSSREF_MAILTO": "me@lab.org"}):
            vcb.set_mailto(None)
            self.assertIn("mailto:me@lab.org", vcb._user_agent())

    def test_flag_overrides_env(self):
        with mock.patch.dict(vcb.os.environ, {"CROSSREF_MAILTO": "env@lab.org"}):
            vcb.set_mailto("flag@lab.org")
            try:
                self.assertIn("mailto:flag@lab.org", vcb._user_agent())
            finally:
                vcb.set_mailto(None)


# ---------------------------------------------------------------------------
# Bug 9: S2_API_KEY env var
# ---------------------------------------------------------------------------

class TestS2Key(unittest.TestCase):
    def test_cli_wins(self):
        with mock.patch.dict(vcb.os.environ, {"S2_API_KEY": "env-key"}):
            self.assertEqual(vcb.resolve_s2_key("cli-key"), "cli-key")

    def test_env_fallback(self):
        with mock.patch.dict(vcb.os.environ, {"S2_API_KEY": "env-key"}):
            self.assertEqual(vcb.resolve_s2_key(None), "env-key")

    def test_none(self):
        with mock.patch.dict(vcb.os.environ, {}, clear=True):
            self.assertIsNone(vcb.resolve_s2_key(None))


# ---------------------------------------------------------------------------
# Bug 10: on-disk cache
# ---------------------------------------------------------------------------

class TestCache(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cache.json"
            c = vcb.VerificationCache(path)
            self.assertIsNone(c.get("doi:10.1/x"))
            c.set("doi:10.1/x", {"success": True, "metadata": {"title": "T"}})
            c.save()
            c2 = vcb.VerificationCache(path)
            self.assertEqual(c2.get("doi:10.1/x"),
                             {"success": True, "metadata": {"title": "T"}})

    def test_corrupt_cache_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "cache.json"
            path.write_text("{not json", encoding="utf-8")
            c = vcb.VerificationCache(path)
            self.assertIsNone(c.get("anything"))

    def test_verifier_uses_cache_and_skips_network(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            bib = tdir / "refs.bib"
            bib.write_text(
                "@article{cached2024,\n"
                "  title = {A Cached Paper},\n"
                "  author = {Smith, John},\n"
                "  journal = {Journal of Testing},\n"
                "  year = {2024},\n"
                "  doi = {10.1234/cached}\n"
                "}\n",
                encoding="utf-8",
            )
            texdir = tdir / "tex"
            texdir.mkdir()
            (texdir / "main.tex").write_text(r"\cite{cached2024}", encoding="utf-8")

            cache_path = tdir / "cache.json"
            cache = vcb.VerificationCache(cache_path)
            cache.set("doi-v2:10.1234/cached", {
                "success": True,
                "metadata": {"title": "A Cached Paper", "year": 2024,
                             "authors": ["John Smith"],
                             "venue": "Journal of Testing"},
            })
            cache.save()

            def boom(*args, **kwargs):
                raise AssertionError("network must not be touched when cached")

            verifier = vcb.BibtexCitationVerifier(
                bib_path=bib, tex_dir=texdir, cache_path=cache_path,
            )
            buf = io.StringIO()
            with mock.patch.object(vcb, "verify_doi", boom), \
                    mock.patch.object(vcb, "search_external", boom), \
                    mock.patch.object(vcb, "verify_url", boom), \
                    mock.patch.object(vcb.time, "sleep"), \
                    contextlib.redirect_stdout(buf):
                passed = verifier.run()
            self.assertTrue(passed)
            self.assertEqual(
                verifier.results["cached2024"]["status"],
                vcb.BibtexCitationVerifier.VERIFIED,
            )

    def test_legacy_doi_cache_entry_is_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            bib = tdir / "refs.bib"
            bib.write_text(
                "@article{fresh2024,\n"
                "  title = {A Fresh Paper},\n"
                "  author = {Smith, John},\n"
                "  journal = {Journal of Testing},\n"
                "  year = {2024},\n"
                "  doi = {10.1234/fresh}\n"
                "}\n",
                encoding="utf-8",
            )
            texdir = tdir / "tex"
            texdir.mkdir()
            (texdir / "main.tex").write_text(r"\cite{fresh2024}", encoding="utf-8")

            cache_path = tdir / "cache.json"
            cache = vcb.VerificationCache(cache_path)
            cache.set("doi:10.1234/fresh", {
                "success": True,
                "metadata": {"title": "A Fresh Paper", "year": 2024,
                             "authors": ["Smith John"],
                             "venue": "Journal of Testing"},
            })
            cache.save()

            doi_lookup = mock.Mock(return_value=(True, {
                "title": "A Fresh Paper",
                "year": 2024,
                "authors": ["John Smith"],
                "venue": "Journal of Testing",
            }))
            verifier = vcb.BibtexCitationVerifier(
                bib_path=bib, tex_dir=texdir, cache_path=cache_path,
            )
            with mock.patch.object(vcb, "verify_doi", doi_lookup), \
                    mock.patch.object(vcb, "search_external") as external_lookup, \
                    mock.patch.object(vcb, "verify_url") as url_lookup, \
                    mock.patch.object(vcb.time, "sleep"), \
                    contextlib.redirect_stdout(io.StringIO()):
                passed = verifier.run()
            self.assertTrue(passed)
            doi_lookup.assert_called_once_with("10.1234/fresh")
            external_lookup.assert_not_called()
            url_lookup.assert_not_called()


class TestAuthorNormalization(unittest.TestCase):
    def test_unicode_and_bibtex_order_are_normalized_symmetrically(self):
        similarity, mismatches = vcb.author_similarity(
            "García, José", ["José Garcia"]
        )
        self.assertEqual(similarity, 1.0)
        self.assertEqual(mismatches, [])

    def test_latex_and_unicode_accents_match_ascii_api_names(self):
        similarity, mismatches = vcb.author_similarity(
            r"Packh{\"a}user, Katharina", ["Katharina Packhauser"]
        )
        self.assertEqual(similarity, 1.0)
        self.assertEqual(mismatches, [])


class TestCitationIdentityRun(unittest.TestCase):
    def _paths(self, root, bib_text, tex=r"\cite{paper}"):
        bib = root / "refs.bib"
        bib.write_text(bib_text, encoding="utf-8")
        texdir = root / "tex"
        texdir.mkdir()
        (texdir / "main.tex").write_text(tex, encoding="utf-8")
        return bib, texdir

    def test_reachable_unrelated_url_cannot_override_missing_author(self):
        with tempfile.TemporaryDirectory() as td:
            bib, texdir = self._paths(
                Path(td),
                "@article{paper,\n"
                "  title = {Identity Matters},\n"
                "  journal = {Journal of Testing},\n"
                "  year = {2024},\n"
                "  url = {https://example.org/unrelated}\n"
                "}\n",
            )
            url_lookup = mock.Mock(return_value=(True, "HTTP 200 OK"))
            ext_meta = {
                "title": "Identity Matters",
                "authors": ["John Smith"],
                "year": 2024,
                "venue": "Journal of Testing",
                "source": "crossref",
                "title_similarity": 1.0,
            }
            verifier = vcb.BibtexCitationVerifier(
                bib_path=bib, tex_dir=texdir, strict=True,
            )
            with mock.patch.object(vcb, "verify_url", url_lookup), \
                    mock.patch.object(vcb, "search_external", return_value=(True, ext_meta)), \
                    mock.patch.object(vcb.time, "sleep"), \
                    contextlib.redirect_stdout(io.StringIO()):
                passed = verifier.run()
            self.assertFalse(passed)
            self.assertEqual(
                verifier.results["paper"]["status"],
                vcb.BibtexCitationVerifier.SUSPICIOUS,
            )
            url_lookup.assert_not_called()

    def test_doi_author_mismatch_is_suspicious(self):
        with tempfile.TemporaryDirectory() as td:
            bib, texdir = self._paths(
                Path(td),
                "@article{paper,\n"
                "  title = {Identity Matters},\n"
                "  author = {Smith, John},\n"
                "  journal = {Journal of Testing},\n"
                "  year = {2024},\n"
                "  doi = {10.1234/identity}\n"
                "}\n",
            )
            doi_meta = {
                "title": "Identity Matters",
                "authors": ["Jane Jones"],
                "year": 2024,
                "venue": "Journal of Testing",
            }
            verifier = vcb.BibtexCitationVerifier(bib_path=bib, tex_dir=texdir)
            with mock.patch.object(vcb, "verify_doi", return_value=(True, doi_meta)), \
                    mock.patch.object(vcb, "search_external", return_value=(False, {"error": "none"})), \
                    mock.patch.object(vcb.time, "sleep"), \
                    contextlib.redirect_stdout(io.StringIO()):
                verifier.run()
            self.assertEqual(
                verifier.results["paper"]["status"],
                vcb.BibtexCitationVerifier.SUSPICIOUS,
            )
            self.assertTrue(
                any("Author mismatch (DOI)" in issue
                    for issue in verifier.results["paper"]["issues"])
            )

    def test_doi_venue_mismatch_is_suspicious(self):
        with tempfile.TemporaryDirectory() as td:
            bib, texdir = self._paths(
                Path(td),
                "@article{paper,\n"
                "  title = {Identity Matters},\n"
                "  author = {Smith, John},\n"
                "  journal = {Journal of Testing},\n"
                "  year = {2024},\n"
                "  doi = {10.1234/identity}\n"
                "}\n",
            )
            doi_meta = {
                "title": "Identity Matters",
                "authors": ["John Smith"],
                "year": 2024,
                "venue": "Proceedings of Unrelated Work",
            }
            verifier = vcb.BibtexCitationVerifier(bib_path=bib, tex_dir=texdir)
            with mock.patch.object(vcb, "verify_doi", return_value=(True, doi_meta)), \
                    mock.patch.object(vcb, "search_external", return_value=(False, {"error": "none"})), \
                    mock.patch.object(vcb.time, "sleep"), \
                    contextlib.redirect_stdout(io.StringIO()):
                verifier.run()
            self.assertEqual(
                verifier.results["paper"]["status"],
                vcb.BibtexCitationVerifier.SUSPICIOUS,
            )
            self.assertTrue(
                any("Venue mismatch (DOI)" in issue
                    for issue in verifier.results["paper"]["issues"])
            )

    def test_doi_unicode_author_match_is_verified(self):
        with tempfile.TemporaryDirectory() as td:
            bib, texdir = self._paths(
                Path(td),
                "@article{paper,\n"
                "  title = {Identity Matters},\n"
                "  author = {García, José},\n"
                "  journal = {Journal of Testing},\n"
                "  year = {2024},\n"
                "  doi = {10.1234/identity}\n"
                "}\n",
            )
            doi_meta = {
                "title": "Identity Matters",
                "authors": ["José Garcia"],
                "year": 2024,
                "venue": "Journal of Testing",
            }
            verifier = vcb.BibtexCitationVerifier(bib_path=bib, tex_dir=texdir)
            with mock.patch.object(vcb, "verify_doi", return_value=(True, doi_meta)), \
                    mock.patch.object(vcb, "search_external") as external_lookup, \
                    mock.patch.object(vcb.time, "sleep"), \
                    contextlib.redirect_stdout(io.StringIO()):
                passed = verifier.run()
            self.assertTrue(passed)
            self.assertEqual(
                verifier.results["paper"]["status"],
                vcb.BibtexCitationVerifier.VERIFIED,
            )
            external_lookup.assert_not_called()

    def test_tex_read_error_fails_even_without_strict_mode(self):
        with tempfile.TemporaryDirectory() as td:
            bib, texdir = self._paths(
                Path(td),
                "@article{paper,\n"
                "  title = {Identity Matters},\n"
                "  author = {Smith, John},\n"
                "  journal = {Journal of Testing},\n"
                "  year = {2024},\n"
                "  doi = {10.1234/identity}\n"
                "}\n",
            )
            (texdir / "unreadable.tex").mkdir()
            doi_meta = {
                "title": "Identity Matters",
                "authors": ["John Smith"],
                "year": 2024,
                "venue": "Journal of Testing",
            }
            verifier = vcb.BibtexCitationVerifier(bib_path=bib, tex_dir=texdir)
            with mock.patch.object(vcb, "verify_doi", return_value=(True, doi_meta)), \
                    mock.patch.object(vcb.time, "sleep"), \
                    contextlib.redirect_stdout(io.StringIO()):
                passed = verifier.run()
            self.assertFalse(passed)
            self.assertTrue(verifier.scan_errors)
            self.assertTrue(any("unreadable.tex" in err for err in verifier.scan_errors))


class TestSummaryEvidenceCounts(unittest.TestCase):
    def test_url_only_evidence_is_excluded_from_verified_total(self):
        verifier = vcb.BibtexCitationVerifier(
            bib_path=Path("refs.bib"), tex_dir=Path("tex")
        )
        verifier.results = {
            "url-only": {
                "status": vcb.BibtexCitationVerifier.URL_VERIFIED,
                "issues": [],
                "url_present": True,
            }
        }
        with contextlib.redirect_stdout(io.StringIO()):
            passed = verifier._step_summary()
        self.assertTrue(passed)
        report = "\n".join(verifier._report_lines)
        self.assertIn("URL present", report)
        self.assertIn("Less than 50% of entries verified (0/1)", report)
        self.assertNotIn("URL verified", report)


# ---------------------------------------------------------------------------
# Integration: full offline run, suspicious entry yields exit code 2 semantics
# ---------------------------------------------------------------------------

class TestOfflineRun(unittest.TestCase):
    def test_suspicious_count_exposed(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            bib = tdir / "refs.bib"
            bib.write_text(
                "@article{generic2020,\n"
                "  title = {A Study of Generic Things},\n"
                "  author = {Smith, John},\n"
                "  year = {2020}\n"
                "}\n",
                encoding="utf-8",
            )
            texdir = tdir / "tex"
            texdir.mkdir()
            (texdir / "main.tex").write_text(r"\cite{generic2020}", encoding="utf-8")

            verifier = vcb.BibtexCitationVerifier(bib_path=bib, tex_dir=texdir)
            buf = io.StringIO()
            with mock.patch.object(
                    vcb, "search_external",
                    lambda *a, **k: (False, {"error": "no results"})), \
                    mock.patch.object(vcb.time, "sleep"), \
                    contextlib.redirect_stdout(buf):
                passed = verifier.run()
            # Non-strict: suspicious does not fail the run, but is counted
            self.assertTrue(passed)
            self.assertEqual(verifier.suspicious_count, 1)
            self.assertEqual(vcb.compute_exit_code(passed, verifier.suspicious_count), 2)


if __name__ == "__main__":
    unittest.main()
