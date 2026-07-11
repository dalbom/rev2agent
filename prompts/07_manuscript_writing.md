# Phase 7: Manuscript Writing

## Objective
Write a complete manuscript draft in LaTeX, ready for submission to the target venue.

## Mode
**Task (subagents)** for parallel section writing, then **direct** for integration and review.

## Current Round Results

Read `current_round` and `current_round_short_name` from `.research_state.json`, require a nonempty short name, and define the Phase 6 result directory once:

```text
round_dir = round{current_round}_{current_round_short_name}
```

Use only `{project_dir}/experiment/results/{round_dir}/comparison_table.md` and `{project_dir}/experiment/results/{round_dir}/comparison_table.json` as the current round's collected numerical sources. Do not fall back to a project-global comparison table.

## Prerequisites
- All experiment results analyzed and confirmed by user (Phase 6 complete).
- Figures generated and saved in `{project_dir}/manuscript/figures/`.
- Statistical tests completed.

## Manuscript Structure

Target format: standard ML conference paper (typically 8 pages + references).

```
{project_dir}/manuscript/
├── main.tex            # FINAL DELIVERABLE: self-contained, all section and
│                       # table content inlined — no \input{} in the final file
├── sections/           # Intermediate artifacts written by subagents (kept)
│   ├── abstract.tex
│   ├── introduction.tex
│   ├── related_work.tex
│   ├── method.tex
│   ├── experiments.tex
│   ├── results.tex
│   ├── discussion.tex
│   └── conclusion.tex
├── figures/
│   ├── fig_main_comparison.pdf
│   ├── fig_ablation.pdf
│   ├── fig_qualitative.pdf
│   └── fig_method_overview.pdf   # placeholder — user may need to create
├── tables/             # LaTeX table fragments generated from comparison_table.json
├── references.bib
└── style/                        # Conference style files (e.g., cvpr.sty)
```

Subagents each write their own `sections/*.tex` file. These are kept as intermediate artifacts, but the integration step (Step 5) produces ONE self-contained `main.tex` with all section and table content inlined. Figures remain external graphics files referenced via `\includegraphics`.

## Step 1: Setup

1. Download the target venue's LaTeX template.
   - Search for the official template (e.g., "CVPR 2026 LaTeX template").
   - If not found, use a standard two-column ML conference template.
2. Set up the `main.tex` with proper preamble, packages, and section structure.
3. Populate `references.bib` from the literature review (Phase 2 outputs).

## Step 2: Anti-Hallucination Protocol (MANDATORY for all writing)

Before ANY section writing begins, establish these ground rules for all subagents:

### Writing Rules for Subagents

Include these rules in EVERY subagent spawn prompt:

```
ANTI-HALLUCINATION RULES (MANDATORY):
1. Every factual claim must have a \cite{} or reference to a table/figure.
2. Use ONLY citation keys from the provided references.bib — do NOT invent new keys.
3. If you need a citation not in references.bib, write: % NEEDS-VERIFICATION: [claim] [suggested source]
4. Copy all numbers from experiment result files — never write numbers from memory.
5. Never use vague attributions ("Studies show...", "Research suggests...", "It is well known...").
   Always name the specific source: "Smith et al. \cite{smith2024} demonstrated..."
6. Clearly distinguish facts from interpretation:
   - FACT: "The AUC improved from 0.65 to 0.77 (Table 2)." — direct from results
   - SYNTHESIS: "This suggests that spatial structure encodes discriminative information." — your interpretation
7. End your section with: % VERIFIED: All citations checked against references.bib
```

### Pre-Writing Checklist

Before spawning section writers, prepare:
1. A finalized `references.bib` with all pre-verified entries
2. The results summary file `{project_dir}/manuscript/results_summary.md`, generated from `{project_dir}/experiment/results/{round_dir}/comparison_table.json` (Phase 6 output). This file is given to EVERY section-writing task — it is the only place section writers may copy numbers from.
3. A list of available figures with their exact filenames and captions
4. **LaTeX table fragments**: convert `{project_dir}/experiment/results/{round_dir}/comparison_table.json` into LaTeX table fragments under `{project_dir}/manuscript/tables/*.tex` (e.g., `main_results.tex`, `ablation.tex`) via a small conversion script. The script must pass the **Code Verification Protocol** (`prompts/05_experiment_execution.md`) before running. **Never hand-type metric values into LaTeX** — every table value flows from the round-scoped `comparison_table.json` through this script.

## Step 3: Parallel Section Writing (via Task Subagents)

Launch subagents for independent sections:

### Task A: Introduction
```
Write sections/introduction.tex

Structure (approximately 1 page):
1. Opening hook: Why is this problem important? (2-3 sentences, broad)
2. Problem statement: What specific problem does this paper address?
3. Limitations of existing work: What's missing? (cite relevant papers)
4. Our approach: Brief description of what we do differently.
5. Contributions: Bulleted list of 3-4 concrete contributions.

Tone: Confident but not overclaiming. Every claim must be supported later in the paper.

Available context:
- Research question: {from state}
- Key papers: {from literature review}
- Our method summary: {from research plan}
- Main results: {from results analysis}

Use \cite{} for all citations. The keys are in references.bib.
```

### Task B: Related Work
```
Write sections/related_work.tex

Structure (approximately 1-1.5 pages):
Organize into 2-4 thematic subsections based on the relevant literature.
For each subsection:
1. Summarize the key approaches and trends.
2. Cite the most important and recent papers.
3. Clearly state how our work differs from or builds upon this line of research.

End with a paragraph positioning our work relative to all discussed work.

Available context:
- Literature review findings: {from {project_dir}/literature/}
- Our method: {from research plan}

IMPORTANT:
- Do NOT just list papers one by one ("X did A. Y did B. Z did C.").
- Group by themes and discuss trends and evolution.
- Be fair and accurate in representing others' work.
```

### Task C: Method
```
Write sections/method.tex

Structure (approximately 2 pages):
1. Problem formulation: Formal notation and definitions.
2. Overview: High-level description of the approach (reference a method figure).
3. Detailed method: Step-by-step description with equations.
4. Implementation details: Architecture choices, hyperparameters, training procedure.

Include:
- Mathematical notation (consistent throughout).
- Algorithm pseudocode if the method involves a non-trivial procedure.
- References to the method overview figure:
  \begin{figure}[t]
  \centering
  % PLACEHOLDER: Method overview diagram
  % Suggestion: A figure showing [describe what would be effective]
  \caption{Overview of our proposed method.}
  \label{fig:method}
  \end{figure}

Available context:
- Research plan method description: {from state}
- Implementation details from experiment scripts
```

### Task D: Experiments & Results
```
Write sections/experiments.tex and sections/results.tex

experiments.tex structure (~1 page):
1. Datasets: Description, splits, preprocessing.
2. Evaluation metrics: Definition and justification.
3. Baselines: List and brief description.
4. Implementation details: Hardware, training time, hyperparameters.

results.tex structure (~1.5 pages):
1. Main results: Reference Table 1, discuss key findings.
2. Ablation study: Reference Table 2, discuss what each component contributes.
3. Qualitative results: Reference qualitative figure if available.
4. Statistical significance: Report p-values for key comparisons.

Tables: reference the pre-generated fragments under {project_dir}/manuscript/tables/
(e.g., \input{tables/main_results.tex}) — these were generated from
comparison_table.json in the Pre-Writing Checklist. NEVER hand-type metric values
into table bodies or inline text; copy inline numbers from results_summary.md only.
(The integration step will inline these fragments into the final main.tex.)
Use \includegraphics for figures.

Available context:
- results_summary.md (sole source for inline numbers)
- Table fragments in {project_dir}/manuscript/tables/
- Figures from {project_dir}/manuscript/figures/
- Statistical test results
```

### Task E: Discussion & Conclusion
```
Write sections/discussion.tex and sections/conclusion.tex

BEFORE WRITING: Read {project_dir}/research_roadmap.md and locate the `## Abandoned` section. For each entry, classify by its `Reason` field and route it to the appropriate manuscript section:

| Reason | Manuscript placement |
|--------|---------------------|
| `out_of_scope` | Limitations (scope boundary — state what the paper does NOT claim to cover) |
| `infeasible` | Limitations (resource / data / time constraint that blocked the direction) |
| `low_value` | Omit by default. Include as a single sentence in Limitations ONLY if a reader of this venue would reasonably expect the direction to be addressed |
| `solved_elsewhere` | Strengthen Related Work (cite the prior/concurrent work that addressed it). Do NOT list as future work |
| `falsified` | DO NOT include as future work. The experiment settled the question — it is not an open problem. Mention only if central to the paper's narrative (e.g., the failure itself is a reported contribution) |

Carry the classified items into the corresponding sections below. If the Abandoned section is empty or the roadmap file does not exist, proceed with Limitations and Future Work drawn from your analysis of the results alone.

discussion.tex (~0.5 page):

PURPOSE: The Discussion INTERPRETS results and POSITIONS the work. It does NOT restate numbers or re-analyze tables — that belongs in Results/Experiments.

STRUCTURE (recommended paragraph order):
1. Positioning — where does this method sit relative to alternatives? Start with the paper's strongest selling point.
2. Key insight — what did the results reveal that is not obvious from the tables alone? Refer to tables by reference, do not restate numbers.
3. Limitations and scope — honest but concise. 2-3 items maximum. Source: Abandoned entries classified as `out_of_scope` or `infeasible` (and `low_value` only if reader-relevant per the classification table above).

WHAT BELONGS IN DISCUSSION:
- Interpretation and synthesis of results (why, not what)
- Comparison to alternative approaches at a conceptual level (e.g., FL vs. feature sharing)
- Practical deployment considerations (1-2 sentences, not operational manuals)
- Connections to theoretical results that contextualize findings
- Concise limitations

WHAT DOES NOT BELONG IN DISCUSSION:
- Restating numbers from tables (refer to "Table X" instead)
- Re-analyzing the same table already discussed in Results
- Detailed security/deployment prescriptions (HSM configuration, key rotation schedules, etc.)
- Introducing new experimental results not shown in any table or figure
- Excessive hedging or defensive language ("we do not claim...", "this should not be interpreted as...")
- Recommending parameter settings already covered in Experiments
- Implementation details for unimplemented extensions (keep to one future-work sentence)

TONE:
- Confident but honest. State what the method achieves, acknowledge what it does not, move on.
- Avoid stacking negatives — one acknowledgment of a limitation is enough.
- Do not use the Discussion as a preemptive rebuttal to imagined reviewers.
- End each paragraph on a forward-looking or positive note, not a caveat.

COMMON MISTAKES TO AVOID:
- Starting with the weakest point or a limitation
- Citing the same theoretical result (e.g., impossibility theorem) more than once across the paper
- Writing a paragraph for each limitation — use a bulleted or compact format
- Mixing deployment advice with algorithmic future work in one paragraph

conclusion.tex (~0.25 page):
1. Brief recap of the contribution — lead with the practical value, not the method name.
2. Key takeaway — one sentence that a reader remembers.
3. Future work directions (2-3 concrete suggestions). Do NOT draw from Abandoned entries marked `falsified` or `low_value` — the former are settled by experiment, the latter were already judged insufficiently valuable. Candidate sources: Pending entries on the roadmap, `solved_elsewhere` entries that this paper's setting could reopen, and open questions surfaced by this paper's results.

Do NOT overclaim. Do NOT introduce new information not supported by experiments.
Do NOT restate numbers already in the abstract — the conclusion should feel like a closing argument, not a summary table.
```

### Task F: Abstract
```
Write sections/abstract.tex

The abstract is written concurrently with the other sections, by its own subagent,
under the same ANTI-HALLUCINATION RULES (included in this prompt like every other
section task): every number must be copied from the provided results_summary.md
(traced to result files) — never from memory — and FACT vs SYNTHESIS must be kept
distinct (no interpretive claim stated as a measured result).

Structure: ONE paragraph (~150-250 words), in this order:
1. Problem — what gap or question the paper addresses (1-2 sentences).
2. Approach — what we do, at a level a non-specialist in the subarea can follow
   (1-2 sentences).
3. Key quantitative result — the single most important number(s), copied exactly
   from results_summary.md, with the comparison point (e.g., "improves mIoU from
   72.3 to 76.2 over the strongest baseline").
4. Implication — why the result matters (1 sentence).

Do NOT cite references in the abstract. Do NOT overclaim beyond what the stated
numbers support.

Available context:
- Research question and positioning: {from state}
- results_summary.md (sole source for all numbers)
```

## Step 4: Quality Gates (MANDATORY)

After all subagents return their sections but before integration, run these three quality gates in sequence. Each gate must pass before proceeding to the next: Automated Validation → Targeted Web Verification → Humanizer Pass.

**Why citation gates matter:** Fabricated or incorrect references are unacceptable in academic work. LLMs are known to hallucinate citation details (wrong titles, wrong authors, wrong venues, wrong page numbers, or entirely nonexistent papers). A single fabricated reference can result in desk rejection, loss of credibility, and accusations of academic misconduct. These are non-negotiable quality gates that MUST complete before presenting any draft to the user.

### Step 4.1: Automated Validation (run the scripts FIRST)

```bash
# 1. Validate manuscript structure, cross-references, and placeholders
python scripts/validate_manuscript.py \
    --manuscript-dir {project_dir}/manuscript/ \
    --bib references.bib \
    --output {project_dir}/manuscript/validation_report.txt

# 2. Verify BibTeX identity (DOI/Crossref/S2 metadata agreement)
#    NOTE: --tex-dir scans the WHOLE manuscript directory, not just sections/ —
#    citations in main.tex must also be checked.
python scripts/verify_citations_bibtex.py \
    --bib {project_dir}/manuscript/references.bib \
    --tex-dir {project_dir}/manuscript/ \
    --strict \
    --output {project_dir}/manuscript/citation_verification.txt

# 3. Check for remaining verification flags
grep -rn "NEEDS-VERIFICATION" {project_dir}/manuscript/
```

The citation verifier requires each identity source (DOI, Crossref, or Semantic Scholar) to provide a nonempty title, at least one usable author, and a year, all agreeing with BibTeX. Venue is optional but must agree when both records provide one. Incomplete source metadata is inconclusive and triggers fallback or `UNVERIFIED`, not a verified status. A reachable URL is not verification evidence and the verifier does not fetch arbitrary URLs from BibTeX. Entries flagged as SUSPICIOUS due to identity or structural mismatches are the most common LLM hallucination type (correct-sounding title, wrong metadata).

**Exit-code semantics:** with `--strict`, the script exits non-zero on any SUSPICIOUS or UNVERIFIED entry. (Without `--strict`, it exits 2 when SUSPICIOUS > 0.) A non-zero exit means the gate has NOT passed.

**Quality gates:**
- `validate_manuscript.py` must report 0 errors (warnings are acceptable)
- `verify_citations_bibtex.py` must exit 0 — no SUSPICIOUS or UNVERIFIED entries remaining (after Step 4.2 resolution)
- No remaining `NEEDS-VERIFICATION` flags (all must be resolved)

### Step 4.2: Targeted Web Verification (SUSPICIOUS / UNVERIFIED entries only)

Web-verify ONLY the entries the script marked `SUSPICIOUS` or `UNVERIFIED` in Step 4.1 — entries the script verified do not need a second manual pass.

For each flagged entry, use a Task subagent with web search access to check against an authoritative source (DBLP, Crossref, Semantic Scholar, ACM DL, IEEE Xplore, arXiv, or the publisher's website):
- Title: exact match (including capitalization nuances)
- Authors: all authors listed, names spelled correctly
- Venue: correct conference/journal name, correct year
- Pages: correct page numbers from the official proceedings (NOT arXiv page numbers)
- Entry type: `@inproceedings` vs `@article` vs `@book` matches the actual publication type

**Handling:**
- `SUSPICIOUS` (metadata mismatch) → MUST be fixed to match the authoritative source, or removed from `references.bib` and the citing text.
- `UNVERIFIED` (script could not confirm the entry exists) → needs manual web confirmation; if it cannot be confirmed against any authoritative source, remove it. If in doubt, ask the user before keeping it.
- **Never guess or reconstruct** citation details from memory. Always look them up.

Save the verification report (each flagged entry → resolution) to `{project_dir}/manuscript/reference_verification.txt`.

**Gate loop:** after fixing/removing entries, re-run Step 4.1. Repeat until all gates pass. **Maximum 5 attempts.** If gates still fail after 5 rounds, present the remaining issues to the user for manual resolution. Only then proceed.

### Step 4.3: Humanizer Pass

After all sections are written and references are verified, review each section to remove signs of AI-generated writing. Academic reviewers and readers are increasingly sensitive to AI writing patterns (inflated language, promotional tone, excessive conjunctive phrases, em dash overuse, etc.).

**Procedure:**
1. For each section file in `sections/`, if the `writing-humanizer` skill is available, run it on the content. Otherwise, manually review for AI writing patterns: inflated language ("groundbreaking", "notable", "crucial"), promotional tone, excessive conjunctive phrases ("Moreover", "Furthermore", "Additionally"), em dash overuse, and formulaic paragraph structures.
2. Review the changes — ensure technical accuracy is preserved (automated or manual edits may occasionally simplify domain-specific phrasing that should stay).
3. Pay special attention to the Introduction and Discussion sections, which are most prone to AI writing patterns.

**This gate runs AFTER automated validation (Step 4.1) and targeted web verification (Step 4.2), but BEFORE integration (Step 5).** The humanizer pass operates on individual section files so that changes are isolated and reviewable.

## Step 5: Integration

After all subagents return their sections AND references are verified AND the humanizer pass is complete:

1. **Assemble** `main.tex` as ONE self-contained file: inline the full content of every `sections/*.tex` file AND every `tables/*.tex` fragment directly into `main.tex`, in final section order. **The final deliverable contains NO `\input{sections/...}` or `\input{tables/...}` statements.** The `sections/*.tex` files are kept on disk as intermediate artifacts, but `main.tex` must compile standalone (plus `references.bib`, `style/`, and the graphics files — `\includegraphics{figures/...}` paths remain as-is; figures are not inlined).
2. **Figure script verification**: If figure/visualization generation scripts exist (e.g., under `{project_dir}/manuscript/figures/`), verify that their experimental configuration matches the project's current default. Scripts that fit models, recompute outcomes, or otherwise produce evidence at runtime are especially prone to config drift. Re-run any script whose config is stale.
3. **Consistency check**:
   - Notation: Are symbols used consistently across sections?
   - Citations: Are all `\cite{}` keys present in `references.bib`?
   - Cross-references: Do all `\ref{}` and `\label{}` match?
   - Table/figure numbering: Consistent and in order of appearance.
4. **Data and semantic provenance**: Create or update `{project_dir}/manuscript/data_provenance.md`. For every evidence-bearing claim in the manuscript (quantitative, qualitative, or theoretical), record the claim, source artifact, generating script or derivation, `evidence_contract_id`, `evidence_contract_fingerprint`, `outcome_id`, and `analysis_protocol_id`. This is the single source of truth for both "where did this evidence come from?" and "what exactly does it measure?"

   Format:
   ```
   - **Gradient attack**: `results/gradient_inversion.json` ← `scripts/run_gradient_inversion.py` ← TEST ✓
   ```

   **Rules:**
   - **Single-run principle.** Each experiment configuration produces ONE canonical result file. All manuscript references (tables, figures, inline text) must cite the same file. Never re-run an experiment that already has a result file unless the protocol has changed — a protocol change requires a new Evidence Contract version and result identity.
   - **Semantic parity.** Comparable cells and claims must use the same Evidence Contract and analysis protocol unless the difference is explicit and justified. A matching metric label is not evidence of matching semantics.
   - **Figure-table consistency.** When a figure and a table report metrics for the same experiment, they must use the same result file. If a figure uses per-image values from a visualization run, inline text must cite the table's canonical values, not the figure's per-sample values.
   - **Runtime-computed values** (values not stored in a result JSON but calculated by a script at runtime) must record the script path AND the configuration used (architecture, dimensions, seeds). These are the highest-risk entries for config drift.
   - **"Qualitative only" is not an exemption** from config consistency. If a figure script uses a different experimental configuration than the project default, it is a bug — not an accepted inconsistency.
   - **No "Known inconsistencies (accepted)" section.** Every inconsistency must instead specify: (a) why it exists, (b) when it will be resolved, and (c) what manuscript content it affects. Use the label "deferred" rather than "accepted."
   - Update `data_provenance.md` whenever a new experiment is run, a default config changes, or manuscript text is modified.
5. **Frozen Reproducibility Bundle (MANDATORY)**: Before the manuscript can
   enter Phase 8, freeze an internal bundle containing the relevant code or
   derivation snapshot, environment, Evidence Contracts, resolved configs,
   commands, data/model identifiers, result hashes, and table/figure generation
   path. An internal independent reviewer must reproduce at least one central
   claim from its source input through the manuscript-facing output.

   Internal reproducibility is mandatory. Public release or supplementary
   submission is conditional on venue policy, legal obligations, privacy,
   licensing, and user authorization; never treat inability to publish an
   artifact as permission to skip the internal reproduction gate.

6. **Compile** the LaTeX. Use the following fallback chain (preferred tool first):

   1. **tectonic** (preferred; path in `.rev2agent_config.json` under `latex.tectonic_path`). Handles bibtex and rerun cycles automatically and downloads missing packages on first use.
      ```bash
      cd {project_dir}/manuscript
      tectonic main.tex
      ```
   2. **latexmk** (if TeX Live / MiKTeX is present — handles bibtex + reruns automatically).
      ```bash
      latexmk -pdf main.tex
      ```
   3. **Manual sequence** (last resort).
      ```bash
      pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
      ```
   4. **No LaTeX toolchain available** → tell the user: "No LaTeX compiler found. Install tectonic (`curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh`) or TeX Live, then re-run Phase 7." **Do NOT attempt to install texlive yourself** — it is massive and may not be what the user wants.
6. **Fix** any compilation errors iteratively.
7. **PDF figure cropping** (optional cosmetic pass). If any figure PDFs have excess whitespace:
   1. `pdfcrop input.pdf output.pdf` (ships with TeX Live) — preferred.
   2. `gs -o output.pdf -sDEVICE=pdfwrite -dPDFSETTINGS=/prepress ... input.pdf` (if Ghostscript is installed).
   3. Python `pypdf` with `trim_box` adjustment.
   4. Skip cropping — it is cosmetic, not required for a valid manuscript.
8. **Page count check**: Is it within the venue's page limit?

## Step 6: Placeholder Figures

For figures that require manual creation (e.g., method overview diagrams):

```
📝 Figure Placeholders
──────────────────────
1. fig_method_overview.pdf
   Suggested content: A diagram showing [describe architecture/pipeline].
   Layout suggestion: [describe ideal layout — e.g., "Left: input data flow,
   Center: processing stages with key components labeled, Right: output"]
   Tools to create: draw.io, PowerPoint, TikZ, or Inkscape.

2. [Other placeholder figures if any]
```

## Output to User

```
📄 Manuscript Draft Complete
──────────────────────────────
Title: [title]
Target venue: [venue]
Page count: [N] pages (limit: [M])
Compilation: ✅ Successful / ❌ Errors (details below)

Sections written:
  ✅ Abstract
  ✅ Introduction
  ✅ Related Work
  ✅ Method
  ✅ Experiments & Results
  ✅ Discussion & Conclusion

References verified:
  ✅ [N]/[N] references verified against external sources
  Report: {project_dir}/manuscript/reference_verification.txt

Figures included:
  ✅ fig_main_comparison.pdf
  ✅ fig_ablation.pdf
  ⬜ fig_method_overview.pdf — PLACEHOLDER (you need to create this)

The manuscript PDF is at: {project_dir}/manuscript/main.pdf
The LaTeX source is a single self-contained file: {project_dir}/manuscript/main.tex
(all sections and tables inlined — no \input{}; figures are separate graphics
files under figures/; per-section drafts are kept under sections/ as
intermediate artifacts)

⚠️ Action items for you:
  1. Create the method overview figure (see suggestions above).
  2. Review the writing — especially the introduction and method sections.
  3. Check all numbers in tables match the experiment logs.
  4. Add acknowledgments if needed.
```

Ask: **"The manuscript draft is ready. Would you like me to revise any specific section, or would you like to review it yourself first?"**

## Phase Summary

After the manuscript draft is complete and presented to the user, write or update:
- **File**: `{project_dir}/summaries/phase7_manuscript.md`
- **Contents**: Title, target venue, page count, sections written, references count, figures included vs. placeholder, compilation status. This is a single file updated each time the manuscript is revised (not per-round).

This file must exist before proceeding to Phase 8.

## State Update

After presenting draft to user:
- `current_phase`: `7`
- `sub_step`: `null`
- `current_round`: unchanged
- `phase_status`: `"waiting_for_user"`
- `project_status`: unchanged
- `manuscript.status`: `"draft_complete"`
- Populate `manuscript.title`, `manuscript.abstract`, `manuscript.latex_path`
- List `manuscript.figures` with status (included vs placeholder)
- Append to `phase_history`

After user confirms ready for review:
- `current_phase`: `8`
- `phase_status`: `"not_started"`
- Append to `phase_history`

## Revision Loop

If the user requests changes:
1. Read the specific feedback.
2. Edit the relevant section in place (or rewrite it if the change is large). Since section content is inlined, apply the edit to `main.tex`; if you also keep `sections/*.tex` in sync, update both.
3. Recompile and present the updated PDF.
4. Repeat until the user is satisfied.
