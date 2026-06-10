# Phase 1: Topic Interview

## Objective
Guide the user from a vague research interest to a well-defined broad topic through a structured conversational interview.

## Mode
Direct conversation with the user. No agents or subagents needed.

## Interview Flow

**Early state creation:** Before starting the interview, create a temporary project directory and state file so that progress is recoverable if the session crashes mid-interview:

1. Create a temporary directory name: `_new_project_draft`
2. Create `_new_project_draft/.research_state.json` using the **FULL schema** from `prompts/conventions.md` — every top-level key present with its default/empty value, so any code reading the draft state never hits missing keys. Set:
   - `project_dir`: `"_new_project_draft"`
   - `current_phase`: `1`
   - `sub_step`: `null`
   - `current_round`: `0`
   - `phase_status`: `"in_progress"`
   - `project_status`: `"active"`
   - `created_at` / `updated_at`: current ISO 8601 UTC timestamp
3. **Interview completion:** after the user confirms the topic, the draft directory is **renamed** to the real `project_dir` (see Project Directory Creation below) and the state file's `project_dir` field is updated to match.
4. **Abandon / start over:** if the user abandons the interview or asks to start over, **DELETE the `_new_project_draft/` directory** before doing anything else. Never leave a stale draft behind.
5. **Session resume:** on session start, if `_new_project_draft/` exists, offer the user a choice: **resume the interview** from the draft, or **discard the draft** (delete the directory and start fresh).

Conduct the interview **one question at a time**. Do not dump all questions at once. Wait for each answer before asking the next. Adapt follow-up questions based on responses.

### Core Questions (ask in order, adapt as needed)

1. **Domain**
   "What research area or topic are you interested in?"
   - If vague (e.g., "AI"), ask for a subfield (e.g., computer vision, NLP, robotics).

2. **Data Modality**
   "What type of data are you working with or interested in?"
   - Examples: images, text, point clouds, video, tabular, multi-modal.

3. **Research Angle**
   "Are you more interested in generation, improvement, analysis, application, or something else?"
   - Help the user distinguish between creating something new vs. improving something existing vs. studying a phenomenon.

4. **Target Application**
   "Is there a specific application domain you care about?"
   - Examples: autonomous driving, medical imaging, robotics, NLP for low-resource languages.

5. **Dataset Preferences**
   "Do you have any specific datasets or benchmarks in mind?"
   - If yes, note them. If no, say you'll identify appropriate ones in the literature search phase.

6. **Constraints & Resources**
   "Are there any constraints I should know about?"
   - Hardware (GPU type, count, memory), time budget, existing codebase to build on, collaborators.

7. **Ambition Level**
   "What venue are you targeting? A top-tier conference (CVPR, NeurIPS, ICML), a workshop, or a journal?"
   - This shapes how novel and rigorous the work needs to be.

8. **Prior Work**
   "Have you read any papers recently that inspired this direction?"
   - If yes, note them as seed papers for Phase 2.

### Adaptive Follow-ups

- If the user gives very specific answers → fewer questions needed, move quickly.
- If the user is exploratory → ask more probing questions, suggest example directions.
- If the user seems uncertain → If the `research-deep-dive` skill is available, use it to discover trending topics, open problems, and promising directions. Otherwise, use web search to research the area manually. Use the research findings to propose 2-3 concrete, evidence-backed directions and let them pick.

## Output

After the interview, produce a **Topic Summary** and present it to the user for confirmation:

```
📝 Topic Summary
────────────────
Broad Area: [e.g., Synthetic Data for Computer Vision]
Specific Interest: [e.g., Using synthetic image data to improve model performance]
Application Domain: [e.g., Autonomous driving]
Data Type: [e.g., Images — urban street scenes]
Candidate Datasets: [e.g., Cityscapes, KITTI, BDD100K]
Target Venue: [e.g., CVPR / ECCV / top-tier CV conference]
Hardware: [e.g., 1x RTX 3090, 50GB storage]
Seed Papers: [any papers the user mentioned]
Constraints: [any noted constraints]
```

Ask: **"Does this look right? Anything you'd like to change before I start searching the literature?"**

## Project Directory Creation

After the user confirms the topic summary, **create the project directory**:

1. **Derive a directory name** from the broad topic. Use lowercase `snake_case` (e.g., "Synthetic Data for Semantic Segmentation" → `synthetic_data_semantic_segmentation`).
2. **Present the proposed name** and let the user accept or modify it:
   ```
   I'll create a project directory: ./synthetic_data_semantic_segmentation/
   Is this name okay, or would you prefer something different?
   ```
3. **Validate the directory name**: The name must match `^[a-z0-9_]+$` (lowercase letters, digits, underscores only) and be at most 50 characters. Reject names containing spaces, hyphens, dots, slashes, or any special characters. If the user proposes an invalid name, sanitize it automatically and confirm.
4. **Rename the draft and create the directory structure**: rename `_new_project_draft/` to `{project_dir}/`, then:
   ```
   mkdir -p {project_dir}/{literature,experiment/{configs,scripts,checkpoints,results,logs,data},manuscript/{figures,tables},summaries}
   ```
5. Set `project_dir` in the state file and use it for all subsequent operations.

## Phase Summary

After user confirms the topic summary and the project directory is created, write:
- **File**: `{project_dir}/summaries/phase1_topic.md`
- **Contents**: Broad area, specific interest, application domain, data type, candidate datasets, target venue, hardware constraints, seed papers, and any noted constraints. This file must be self-contained and readable without the state file.

This file must exist before proceeding to Phase 2.

## State Update

Field names and enum values follow `prompts/conventions.md`. After user confirms and project directory is created:
- `project_dir`: the final directory name (draft renamed)
- `current_phase`: `2`
- `sub_step`: `null`
- `current_round`: `0`
- `phase_status`: `"not_started"`
- `project_status`: `"active"`
- Populate `topic.broad_topic`, `topic.target_dataset`, etc.
- Append to `phase_history` (entry format in `prompts/conventions.md`)

Then proceed to Phase 2 by reading `prompts/02_literature_search.md`.
