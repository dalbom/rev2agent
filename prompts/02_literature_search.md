# Phase 2: Literature Search & Topic Narrowing

## Objective
Search the literature broadly, identify promising research gaps, and narrow down to a specific, publishable research question.

## Mode
**Parallel Agents** — multiple agents explore different angles independently, then the lead synthesizes findings.

## Prerequisites
- Phase 1 completed with a confirmed broad topic in `{project_dir}/.research_state.json`.

## Agent Structure

Spawn 4 independent Agent subagents, each working independently and writing its findings to a file. No inter-agent messaging is needed — the lead reads all output files after agents complete.

### Agent Roles

1. **survey-agent**
   - Role: Find the most recent and highly-cited survey papers on the broad topic.
   - Action: Search arXiv, Semantic Scholar, Google Scholar via web search.
   - Deliverable: List of 5-10 survey papers with key takeaways and identified sub-areas.
   - Output file: `{project_dir}/literature/survey-agent.md`

2. **frontier-agent**
   - Role: Find the most recent papers (last 12 months) pushing the frontier.
   - Action: Search for papers from target venues (CVPR, NeurIPS, ECCV, ICLR, etc.) on the topic.
   - Deliverable: List of 10-15 recent papers with their contributions and stated future work/limitations.
   - Output file: `{project_dir}/literature/frontier-agent.md`

3. **gap-agent**
   - Role: Identify research gaps, underexplored combinations, and future work directions.
   - Action: Cross-reference findings from survey-agent and frontier-agent. Look for:
     - Future work sections that haven't been addressed yet.
     - Combinations of methods/datasets that haven't been tried.
     - Contradictory findings between papers.
     - Promising methods tested only in narrow settings.
   - Deliverable: Ranked list of 5-8 potential research directions with feasibility assessment.
   - Output file: `{project_dir}/literature/gap-agent.md`

4. **baseline-agent**
   - Role: Identify existing baselines and SOTA results on candidate datasets.
   - Action: Find leaderboards, benchmark results, and standard evaluation protocols.
   - Deliverable: Table of current SOTA methods and results on relevant datasets/metrics.
   - Output file: `{project_dir}/literature/baseline-agent.md`

### Coordination

The lead spawns all 4 agents in parallel. After all agents complete, the lead reads their output files and synthesizes findings.

## Spawn Prompts

When spawning agents, include this context in each spawn prompt:

```
PROJECT CONTEXT:
- Broad topic: {topic.broad_topic}
- Specific interest: {topic.specific_topic}
- Application domain: {relevant domain}
- Candidate datasets: {topic.target_dataset}
- Target venue: {topic.target_venue}
- Seed papers: {any seed papers from Phase 1}

YOUR ROLE: {role description}
YOUR TASK: {specific task description}
DELIVERABLE: {what to produce}
OUTPUT: Write your findings to {project_dir}/literature/{your-role-name}.md
```

## Search Strategy

### Deep Research Integration

**Before launching the agents**, if the `/deep-research` skill is available, use it on the broad topic to conduct a comprehensive multi-source literature analysis. Otherwise, use WebSearch to manually research the area with multiple parallel queries. Either approach provides:
- 10+ verified sources with citation tracking
- Comparison of competing approaches
- Identification of research gaps and trends
- A structured research report with verified claims

Use the research output as the **seed knowledge base** for the agents. Share the research report with all agents in their spawn prompts so they can build on verified findings rather than starting from scratch.

### Parallel Search Protocol

Each agent should execute multiple searches concurrently for maximum coverage. Launch 5-10 independent searches in a single message using the WebSearch tool.

**Query decomposition — break the research topic into orthogonal search angles:**

1. **Core topic (broad)** — Main concept overview
2. **Core topic (recent)** — Latest work from the past 12 months
3. **Technical details** — Specific methods, architectures, implementations
4. **Academic sources** — Papers from target venues (CVPR, NeurIPS, ICLR, etc.)
5. **Critical analysis** — Limitations, failure modes, negative results
6. **Alternative approaches** — Competing methods, different paradigms
7. **Datasets & benchmarks** — Standard evaluation protocols, leaderboards
8. **Application domains** — Real-world use cases, industry adoption

**Example parallel execution (single message, multiple tool calls):**

```
[Launch ALL of these simultaneously]
WebSearch(query="survey {topic} 2024 2025")
WebSearch(query="site:arxiv.org {topic} {specific_method} 2025")
WebSearch(query="{topic} limitations challenges failure")
WebSearch(query="{topic} benchmark SOTA leaderboard")
WebSearch(query="{topic} {alternative_approach} comparison")
WebSearch(query="CVPR NeurIPS ICLR 2025 {topic}")
```

**After initial searches, spawn deep-dive agents in parallel:**

```
Task(description="Survey paper analysis", prompt="Read and summarize top survey papers on {topic}")
Task(description="Recent frontier papers", prompt="Analyze latest papers from 2024-2025 on {topic}")
Task(description="Baseline collection", prompt="Collect SOTA results and baselines for {datasets}")
```

### First Finish Search (FFS) Quality Gates

Proceed to the next step when FIRST threshold is reached:

| Mode | Sources Required | Min Credibility | Time Limit |
|------|-----------------|-----------------|------------|
| Quick | 10+ sources | Avg >60/100 | 5 min |
| Standard | 15+ sources | Avg >60/100 | 10 min |
| Deep | 25+ sources | Avg >70/100 | 20 min |

Continue remaining searches in background — additional sources strengthen Phase 4 (Synthesis & Decision).

### Source Credibility Scoring

Score every source using the credibility evaluator (`scripts/source_evaluator.py`):

```python
from scripts.source_evaluator import SourceEvaluator
evaluator = SourceEvaluator()
score = evaluator.evaluate_source(url=url, title=title, publication_date=date, author=author)
# score.overall_score: 0-100
# score.recommendation: "high_trust" / "moderate_trust" / "low_trust" / "verify"
```

**Credibility requirements:**
- Core claims must be supported by sources scoring >70/100
- Flag any source scoring <40 for additional verification
- Maintain source diversity: at least 3 source types (academic, industry, technical docs)
- Record credibility scores in the paper information alongside other metadata

### Paper Information to Collect

For each paper found, record:
- Title, authors, year, venue
- Key contribution (1-2 sentences)
- Method summary
- Datasets used
- Results (key numbers)
- Limitations / future work (verbatim quotes when possible)
- Relevance to our topic (high/medium/low)
- URL (arXiv link preferred)
- **Credibility score** (from source_evaluator.py)
- **Verified BibTeX entry** (see below)

### Reference Accuracy (MANDATORY)

**CRITICAL: NEVER write citation details (title, authors, venue, pages) from memory.** LLMs are known to hallucinate citation metadata — inventing plausible-sounding titles, wrong author names, incorrect page numbers, or even entirely nonexistent papers. This is academically unacceptable.

For every paper you intend to cite:
1. **Look it up** on DBLP, Semantic Scholar, Google Scholar, or the publisher's website.
2. **Copy the BibTeX entry** from an authoritative source (DBLP is preferred for conferences).
3. If you cannot find a verifiable BibTeX entry, **flag the paper** and note that the citation needs manual verification.
4. **Never reconstruct** a BibTeX entry from memory. Even if you're confident, look it up.

Save all collected BibTeX entries to `{project_dir}/literature/collected_references.bib` as they are found. This file will be the source of truth for Phase 7 (Manuscript Writing).

## Synthesis & Decision

After all agents complete and the lead has read their output files, the lead should:

1. **Compile** all future work directions and research gaps.
2. **Assess source quality**: Run credibility scores on all collected sources.
   ```bash
   python scripts/source_evaluator.py --batch {project_dir}/literature/sources.json --output {project_dir}/literature/credibility_scores.json
   ```
   Discard or flag any findings supported only by low-credibility sources (<40).
3. **Score** each direction on:
   - Novelty (1-5): How new is this direction?
   - Feasibility (1-5): Can it be done with available resources?
   - Impact (1-5): How significant would the contribution be?
   - Publishability (1-5): How likely is this to be accepted at the target venue?
   - Evidence strength (1-5): How well-supported by high-credibility sources?
4. **Rank** directions by total score (now out of 25 instead of 20).
5. **Recommend** the top 2-3 directions to the user.

## Output to User

Present a structured summary:

```
Literature Search Results
─────────────────────────────
Papers Reviewed: [N]
Source Credibility: Avg [X]/100, High-trust: [N], Low-trust: [N]
Key Surveys: [list top 3]

Top Research Directions (Ranked)

1. [Direction Title] — Score: X/25
   Gap: [what's missing in the literature]
   Approach: [proposed high-level approach]
   Feasibility: [why this is doable]
   Evidence: [N] supporting sources, avg credibility [X]/100
   Risk: [main risk or challenge]

2. [Direction Title] — Score: X/25
   ...

3. [Direction Title] — Score: X/25
   ...

Current SOTA on Target Datasets
[Table of baselines]

Recommendation: Direction [N] because [reasoning].
```

Ask: **"Which direction would you like to pursue? Or would you like me to explore any of these further?"**

## Phase Summary

After user confirms the selected direction, write:
- **File**: `{project_dir}/summaries/phase2_literature.md`
- **Contents**: Papers reviewed (with credibility scores), key surveys, research gaps identified, ranked directions, selected direction with rationale, SOTA baselines table.

This file must exist before proceeding to Phase 3.

## State Update

After user confirms direction:
- `current_phase`: `3`
- `sub_step`: `null`
- `current_round`: `0`
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- Populate `topic.specific_topic`, `topic.research_question`
- Populate `literature.papers_reviewed`, `literature.future_work_ideas`, `literature.selected_direction`
- Append to `phase_history`
