"""Tests for scripts/validate_manuscript.py."""

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_manuscript as vm  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MANUSCRIPT = FIXTURES / "manuscript"


class TestGraphicspath(unittest.TestCase):
    """Bug 19: standard \\graphicspath{{figures/}{plots/}} must work."""

    def test_figure_resolved_via_graphicspath(self):
        tex_files = vm.collect_tex_files(MANUSCRIPT)
        issues = vm.check_figures(tex_files, MANUSCRIPT, MANUSCRIPT)
        errors = [i for i in issues if i.level == "ERROR"]
        self.assertEqual(errors, [], f"unexpected figure errors: {errors}")

    def test_missing_figure_still_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "main.tex").write_text(
                "\\graphicspath{{figures/}}\n"
                "\\includegraphics{nonexistent_plot}\n",
                encoding="utf-8",
            )
            tex_files = vm.collect_tex_files(tdir)
            issues = vm.check_figures(tex_files, tdir, tdir)
            errors = [i for i in issues if i.level == "ERROR"]
            self.assertEqual(len(errors), 1)
            self.assertIn("nonexistent_plot", errors[0].message)


class TestMultiLabelRefs(unittest.TestCase):
    """Bug 20: \\cref{fig:a,fig:b} must be split into separate labels."""

    def test_cref_comma_split(self):
        tex_files = vm.collect_tex_files(MANUSCRIPT)
        refs = vm.extract_refs(tex_files, MANUSCRIPT)
        self.assertIn("fig:a", refs)
        self.assertIn("fig:b", refs)
        self.assertNotIn("fig:a,fig:b", refs)

    def test_starred_cref_recognized(self):
        tex_files = vm.collect_tex_files(MANUSCRIPT)
        refs = vm.extract_refs(tex_files, MANUSCRIPT)
        self.assertIn("tab:results", refs)

    def test_no_false_undefined_errors(self):
        tex_files = vm.collect_tex_files(MANUSCRIPT)
        issues = vm.check_cross_references(tex_files, MANUSCRIPT)
        errors = [i for i in issues if i.level == "ERROR"]
        self.assertEqual(errors, [], f"unexpected cross-ref errors: {errors}")

    def test_truly_undefined_still_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "main.tex").write_text(
                "\\label{fig:exists}\n"
                "\\cref{fig:exists,fig:missing}\n",
                encoding="utf-8",
            )
            tex_files = vm.collect_tex_files(tdir)
            issues = vm.check_cross_references(tex_files, tdir)
            errors = [i for i in issues if i.level == "ERROR"]
            self.assertEqual(len(errors), 1)
            self.assertIn("fig:missing", errors[0].message)


class TestHappyPath(unittest.TestCase):
    def test_fixture_manuscript_has_no_errors(self):
        tex_files = vm.collect_tex_files(MANUSCRIPT)
        bib_path = MANUSCRIPT / "references.bib"

        all_issues = []
        all_issues.extend(vm.check_citations(tex_files, bib_path, MANUSCRIPT))
        all_issues.extend(vm.check_cross_references(tex_files, MANUSCRIPT))
        all_issues.extend(vm.check_required_sections(tex_files))
        all_issues.extend(vm.check_placeholders(tex_files, MANUSCRIPT))
        all_issues.extend(vm.check_figures(tex_files, MANUSCRIPT, MANUSCRIPT))
        all_issues.extend(vm.check_environment_matching(tex_files, MANUSCRIPT))
        all_issues.extend(vm.check_empty_sections(tex_files, MANUSCRIPT))

        errors = [i for i in all_issues if i.level == "ERROR"]
        self.assertEqual(errors, [], f"unexpected errors: {errors}")

    def test_environment_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as td:
            tdir = Path(td)
            (tdir / "main.tex").write_text(
                "\\begin{figure}\n\\end{table}\n", encoding="utf-8")
            tex_files = vm.collect_tex_files(tdir)
            issues = vm.check_environment_matching(tex_files, tdir)
            errors = [i for i in issues if i.level == "ERROR"]
            self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
