# Phase 8: Manuscript Review Panel

## Purpose

Before finalizing a manuscript, run a simulated peer review with a panel of AI agents, each adopting a distinct reviewer persona. This catches issues that a single-perspective review misses: statistical validity, fairness of comparison, technical correctness, logical coherence, and presentation quality.

## When to Trigger

- After the manuscript draft is considered "feature-complete" (all experiments done, all sections written, all references verified).
- Before submitting to a venue or declaring the research complete.
- Can be re-run after a major revision to check whether reviewer concerns were addressed.

## Review Panel Composition

Use **5 reviewer roles** as isolated host-native subagents; the **main agent
acts as Editor-in-Chief** to synthesize and implement changes. Apply
`prompts/agent_workflow.md` for bounded waves and unavailable-reviewer handling.
The independent panel gate remains pending without eligible reviewers.

| Reviewer | Persona | Primary Focus |
|----------|---------|---------------|
| **A** | Methodologist / Statistician | Reproducibility, experimental controls, statistical validity, information leakage, confidence intervals |
| **B** | Fairness & Comparison Critic | SOTA comparison fairness, benchmark limitations, overclaiming, label accuracy |
| **C** | Domain Expert | Technical correctness, methodology soundness, missing related work, positioning in the field |
| **D** | Skeptical Reader / Novelty Critic | Logical gaps, overclaiming, spin detection, novelty assessment, contribution significance, alternative explanations, ethics (if venue requires) |
| **E** | Writing & Presentation Specialist | Clarity, structure, redundancy, figure/table effectiveness, notation consistency, abstract-intro-conclusion alignment |

## Reviewer Independence Protocol

In every review cycle, including re-runs after revision, each reviewer agent
MUST start with fresh context. Do not inherit the editor's conversation,
implementation rationale, or other reviewers' verdicts. Supply the bounded
inputs below explicitly:

1. **Do NOT include** previous review files (`manuscript/reviews/reviewer_*.md`) in the reviewer's spawn prompt — and instruct reviewers NOT to read `manuscript/reviews/` themselves.
2. **Do NOT include** `review_synthesis.md` or `review_response.md` from prior rounds.
3. **Do NOT include** `summaries/phase8_review.md` — when reviewers read `summaries/` for context, this file is explicitly excluded, otherwise cycle-2 reviewers see cycle-1 verdicts.
4. Each reviewer receives ONLY:
   - The current manuscript files (`main.tex` + `sections/`)
   - `references.bib`
   - The context files listed in "Common Instructions for All Reviewers" below
   - Their persona description and rubric
5. The **Editor-in-Chief MAY reference** prior reviews during synthesis (to check whether previously raised issues were addressed), but individual reviewers must not see them.

This prevents anchoring bias where reviewers fixate on issues they previously raised rather than evaluating the manuscript on its current merits.

## Reviewer Instructions Template

Each reviewer agent receives:

1. **Persona description** — who they are and what they prioritize
2. **File list** — all manuscript `.tex` files to read (main.tex + all files in sections/)
3. **Review rubric** — specific questions to answer for their focus area
4. **Output format** — structured review with: Overall Assessment, Major Issues (numbered), Minor Issues (numbered), Specific Line-Level Suggestions, Score (Accept / Minor Revision / Major Revision / Reject)

### Common Instructions for All Reviewers

```
You are reviewing an academic manuscript for [{target_venue}].
You have NOT seen any prior review of this manuscript. Evaluate it fresh.

READ ALL of the following files carefully before writing your review:
- {project_dir}/manuscript/main.tex (or all .tex files if split into sections/)
- {project_dir}/manuscript/references.bib

Also read these context files if relevant to your review focus:
- {project_dir}/.research_state.json (experiment history)
- {project_dir}/research_roadmap.md (research directions)
- {project_dir}/summaries/ (round summaries for experiment details) — EXCLUDING summaries/phase8_review.md, and never read manuscript/reviews/ from prior cycles
- {project_dir}/manuscript/data_provenance.md (number-to-source mapping, if it exists)
- Any figure generation scripts under {project_dir}/manuscript/figures/*.py (check that their experimental config matches the project default)

YOUR REVIEW MUST follow this structure:

## Overall Assessment
2-3 sentence summary of the paper's strengths and weaknesses from your perspective.

## Structural Audit
Complete the mandatory structural checklist (see below) BEFORE writing your review.

## Major Issues
Numbered list. These are problems that MUST be addressed before publication.
For each: describe the issue, explain why it matters, suggest a fix.

## Minor Issues
Numbered list. These are suggestions that would improve the paper but are not blockers.

## Specific Suggestions
Line-level or section-level concrete suggestions (e.g., "In Section 3.2, the claim X should be hedged because...").

## Score
One of: Accept / Minor Revision / Major Revision / Reject
With 1-sentence justification.
```

### Mandatory Structural Audit (ALL Reviewers)

Every reviewer MUST complete this checklist before writing their review. Report any failures as Major Issues.

**1. Every result must have a setup.**
For each quantitative result (reported scores, error rates, correlations, resource measurements, etc.) in the manuscript:
- Is the experimental methodology (what was done, how) described before the result appears?
- Is the motivation (why this experiment) stated?
- If the setup is in a different section, is there an explicit cross-reference?
Flag any result that appears without prior setup description.

**2. Every claim must trace to evidence.**
For each factual claim in the manuscript:
- Does it cite a specific table, figure, or reference?
- If it cites a number, can that number be found in a table/figure?
- Are there numbers in the text that appear nowhere in any table or figure?
- Does `data_provenance.md` link the claim to an Evidence Contract, outcome, and analysis protocol?
- Does the manuscript describe the same unit, procedure, comparison, and claim scope as that contract?
Flag any orphan numbers (quantitative claims not backed by tables/figures).

**3. Content belongs in the right section.**
- Experimental setup (datasets, metrics, baselines, protocols) belongs in the setup section.
- Quantitative results (numbers, comparisons) belong in results sections.
- Qualitative results (visualizations, examples) belong in qualitative/analysis sections.
- Discussion should interpret results, not introduce new experiments.
- Conclusion should summarize, not introduce new claims.
Flag any content that appears in the wrong section.

**4. No redundant or contradictory statements.**
- Is the same result stated in multiple places? If so, are the numbers consistent?
- Do different sections make contradictory claims?
- Are there duplicated explanations that could be consolidated?
- Is the same analysis performed in two different sections? For example, if a results section discusses ablation findings AND a separate ablation section re-analyzes the same table, the analysis should appear in only one place. The other section should cross-reference it.
- Are key numbers (overhead, accuracy drop, etc.) repeated excessively? State a number in its natural home (method section, results table) and reference it elsewhere rather than restating it verbatim.
Flag any inconsistencies or redundancies between sections.

**5. Tables and figures are complete and referenced.**
- Is every table/figure referenced in the text?
- Does every table/figure have a caption that explains it without needing to read the text?
- Are table column headers and units clear?
- Do table values match the numbers cited in the text?
- Are tables discussed in order? If the text references Table 3, then Table 4, then Table 3 again within the same paragraph or subsection, the discussion is disorganized. Each table should be fully discussed before moving to the next.
Flag any unreferenced tables/figures, mismatched values, or out-of-order table references.

**6. Abstract-Introduction-Conclusion alignment.**
- Do all three sections tell the same story?
- Are the contributions listed in the introduction actually delivered?
- Does the conclusion introduce claims not in the abstract or results?
- Are quantitative claims in the abstract supported by the experiments?
Flag any misalignment.

### Persona-Specific Rubric

**Reviewer A (Methodologist):**
- Are all hyperparameters, random seeds, and data splits fully specified for reproducibility?
- Is the evaluation protocol appropriate? Are there hidden confounds?
- Are performance differences statistically significant? Are confidence intervals or p-values reported?
- Is there any risk of information leakage between training and evaluation?
- Are error bars reported consistently across all tables?
- Could an independent researcher replicate the full pipeline from the paper alone?
- If figure generation scripts exist, do their experimental configurations match the paper's stated default?

**Reviewer B (Fairness & Comparison Critic):**
- Are baseline comparisons fair (same conditions, same data, same evaluation protocol)?
- Are we cherry-picking favorable baselines or omitting stronger ones?
- If a baseline is used under non-standard conditions, is this clearly disclosed?
- Does evaluating on limited benchmarks restrict the conclusions?
- Are computational cost comparisons fair (same hardware, batch sizes)?
- Are claims of superiority adequately hedged when differences are small?

**Reviewer C (Domain Expert):**
- Is the technical methodology sound for this domain?
- Are there important related works missing (especially recent papers)?
- Does the paper correctly position itself relative to the literature?
- Are domain-specific evaluation protocols followed?
- Are the limitations acknowledged appropriate and complete?

**Reviewer D (Skeptical Reader / Novelty Critic):**
- Is the contribution significant enough for the target venue?
- Is this genuinely novel, or incremental over existing work? Could a reader say "this is just X + Y"?
- What is the strongest competing paper, and how clearly does this work differentiate itself?
- Are there logical gaps in the argumentation chain?
- Are there claims in the abstract/conclusion not directly supported by experimental evidence?
- Are alternative explanations adequately considered?
- Is the framing honest, or does it spin neutral/negative results as positive?
- Would a domain expert find the threat model / problem formulation realistic?
- If the target venue requires a broader impact / ethics statement, is it adequate?

**Reviewer E (Writing & Presentation):**
- Is the narrative structure clear and easy to follow?
- Are abstract, introduction, and conclusion consistent in their claims and framing?
- Is there excessive redundancy between sections?
- Are figures and tables well-designed, properly captioned, and necessary?
- Is mathematical notation consistent throughout?
- Is the paper an appropriate length for the target venue?
- Are there passages that are unclear, overly dense, or could be simplified?
- Does the contributions list in the introduction match the actual paper content?

## Two-Pass Review Protocol

Phase 8 uses a **two-pass** approach. Pass 1 catches global issues; Pass 2 drills into each section with targeted questions auto-generated from Pass 1 findings.

### Pass 1: Global Review (5 isolated reviewers)

Each of the 5 isolated reviewers evaluates the full manuscript with the
structural audit checklist and their persona-specific rubric.

### Pass 2: Section-by-Section Deep Dive (Editor-in-Chief)

After collecting Pass 1 reviews, the Editor-in-Chief performs a section-by-section audit. For EACH major section (Introduction, Method, Experiments, Discussion, Conclusion), ask:

**Introduction:**
- Does it state the problem, gap, and contribution clearly in that order?
- Does it promise anything that the paper does not deliver?
- Is the motivation self-contained (a reader should understand "why" without reading Related Work)?

**Method:**
- Can someone reimplement the method from the description alone?
- Are all symbols defined before use?
- Are design choices justified (why this architecture, this activation, this default)?

**Experiments/Results:**
- Does each table/figure have a setup described before it and a discussion after it?
- Are tables discussed in order (no jumping back to an earlier table)?
- Is each analysis in exactly one place (not split across Results and Discussion)?

**Discussion:**
- Does it interpret rather than restate?
- Does it avoid restating numbers already in tables?
- Does it start with the paper's strongest point?
- Are limitations concise (2-3 items, not an exhaustive list)?
- Does it mix deployment advice with algorithmic analysis? (These should be separate or omitted.)
- Does it cite the same reference more than once across the paper for the same purpose?

**Conclusion:**
- Does it lead with practical value, not method name?
- Does it avoid restating numbers from the abstract verbatim?
- Is it a closing argument, not a summary table?

**Cross-section checks:**
- Is any key number (overhead, accuracy drop, etc.) stated more than 3 times?
- Is any theoretical result cited more than twice?
- Does any section contain content that belongs in a different section?

Issues found in Pass 2 are added to the synthesis with "Pass 2" tag and treated with the same priority as Pass 1 consensus issues.

## Claim Challenge Ledger (MANDATORY)

Before synthesis, create or update
`{project_dir}/manuscript/claim_challenges.md`. For every central claim, record
claim-relevant contradictory results, failed controls, unfavorable baselines,
robustness or generalization failures, unresolved reviewer objections, and
plausible alternative explanations. Link each challenge to its evidence.

Each challenge must end in exactly one resolution state:

- `resolved_by_evidence` — new evidence answers it;
- `claim_narrowed` — the manuscript scope is reduced accordingly;
- `limitation_disclosed` — the claim remains defensible with an explicit limit;
- `research_redirected` — the project routes to new experiments or reframing;
- `claim_withdrawn` — the unsupported claim is removed.

`out_of_scope` alone is not a resolution when the challenge bears directly on
a central claim. If any unresolved challenge bears directly on a central claim,
the manuscript must not proceed to completion or submission; route it to the
owning phase instead.

## Editor-in-Chief Synthesis

After both passes:

1. **Triage**: Classify each issue as:
   - **Consensus** (3+ reviewers agree, or Pass 2 finding) -> Must address
   - **Majority** (2 reviewers agree) -> Should address
   - **Individual** (1 reviewer) -> Evaluate on merit

2. **Prioritize**: Rank issues by:
   - Structural issues (content in wrong section, missing setup for results) -> Highest priority
   - Correctness issues (factual errors, statistical problems, inconsistent numbers) -> Highest priority
   - Fairness issues (comparison, overclaiming) -> High priority
   - Clarity issues (writing, structure) -> Medium priority
   - Cosmetic issues (formatting, minor wording) -> Low priority

3. **Action Plan**: For each issue, decide:
   - **Accept**: Implement the suggested fix
   - **Partially accept**: Implement a modified version with justification
   - **Reject**: Explain why the suggestion is not applicable

   Update the Claim Challenge Ledger for every issue affecting a central claim.
   The synthesis must account for individual high-severity evidence on its
   merits; reviewer vote count cannot erase contradictory evidence.

4. **Implement**: Apply authorized manuscript corrections. Changes to the
   research question, Evidence Contract, interpretation, or experiment plan
   require the owning approval gate under `prompts/agent_workflow.md`; do not
   launch new experiments from Phase 8.

5. **Verification**: Re-compile LaTeX and run validation checks.

6. **Response Document**: Write a structured response to each reviewer's major issues (like a real revision response letter), saved to `{project_dir}/manuscript/review_response.md`.

## Output Files

- `{project_dir}/manuscript/reviews/reviewer_A.md` — Individual review
- `{project_dir}/manuscript/reviews/reviewer_B.md` — Individual review
- `{project_dir}/manuscript/reviews/reviewer_C.md` — Individual review
- `{project_dir}/manuscript/reviews/reviewer_D.md` — Individual review
- `{project_dir}/manuscript/reviews/reviewer_E.md` — Individual review
- `{project_dir}/manuscript/review_synthesis.md` — Editor synthesis + action plan
- `{project_dir}/manuscript/review_response.md` — Author response to reviews
- `{project_dir}/summaries/phase8_review.md` — Phase summary (**REQUIRED** — listed in the summary checklist in `prompts/conventions.md`; it must exist before moving past Phase 8. Single file, updated across review cycles.)

Write `phase8_review.md` after the Editor-in-Chief synthesis is complete and before presenting the synthesis to the user.

## State Updates

On entering Phase 8:
- `current_phase`: `8`
- `phase_status`: `"in_progress"`
- `manuscript.status`: `"in_review"` (enum in `prompts/conventions.md`)
- Append to `phase_history`

When synthesis is ready:
- `phase_status`: `"waiting_for_user"`

After user approves and changes are implemented:
- `phase_status`: `"completed"`
- Append to `phase_history`

**Re-run limit:** Maximum 5 review cycles. If issues persist after 5 cycles, present remaining issues to the user for manual resolution.

**Routing after fixes:**
- Text changes only → `current_phase`: `7`, `phase_status`: `"not_started"`. Stay in Phase 7/8 revision loop.
- New experiments needed → `current_phase`: `6`, `sub_step`: `"review_reentry"`, `phase_status`: `"not_started"`. Phase 6 enters its **Phase 8 re-entry mode** (see `prompts/06_result_analysis.md`): it skips the analysis steps and goes straight to Round Planning, seeding candidate directions from `manuscript/review_synthesis.md`. Preserve both `current_round` and `current_round_short_name` here; they identify the last completed round until Phase 6 confirms and persists the next round. Do NOT increment or rename the round in Phase 8.
- All issues resolved, the independent panel completed, and the user approved → `phase_status`: `"completed"`, `project_status`: `"completed"`, `manuscript.status`: `"final"` (enum in `prompts/conventions.md`). Manuscript is ready for submission. This status does not authorize external submission or publication.
