# Job Finder Agent — ADK 2.0 Graph Workflow

Build a full ADK 2.0 `Workflow` graph for job finding, with function nodes wired by edges, a human-in-the-loop `RequestInput` pause, and strict Python/LLM split per spec.

---

## Proposed Changes

### File & Folder Layout

```
job_finder_agent/
├── __init__.py                 # exposes root_agent
├── agent.py                    # Workflow(..., edges=[...]) definition
├── config.py                   # all thresholds, model name, weights
├── schemas.py                  # shared Pydantic models (all node I/O)
├── nodes/
│   ├── __init__.py
│   ├── cv_parser.py            # PDF text extraction + LLM normalize
│   ├── planner.py              # pure-Python search param derivation
│   ├── job_search.py           # calls JobSpy MCP; normalizes postings
│   ├── matching.py             # hybrid Python+LLM scoring & ranking
│   ├── skill_gap.py            # top-N LLM skill-gap analysis
│   ├── human_select.py         # RequestInput pause node
│   └── cover_letter.py         # single-posting LLM draft + word-count
└── mcp_servers/
    └── jobspy_client.py        # thin async wrapper around JobSpy MCP SSE
```

---

### [NEW] `job_finder_agent/config.py`

All tunables in one place:

```python
MODEL_NAME          = "gemini-2.0-flash-lite"   # only model used in graph
TOP_N_POSTINGS      = 10      # postings passed to skill-gap node
SKILL_BASELINE_MAX  = 60      # max points from Python keyword overlap
LLM_DELTA_MIN       = -10     # min LLM adjustment
LLM_DELTA_MAX       = 40      # max LLM adjustment
SCORE_MIN           = 0
SCORE_MAX           = 100
COVER_LETTER_MIN_WORDS = 250
COVER_LETTER_MAX_WORDS = 400
JOBSPY_SSE_URL      = "http://localhost:9423"
```

---

### [NEW] `job_finder_agent/schemas.py`

Pydantic BaseModels for every node boundary:

| Model | Used by |
|---|---|
| `ParsedCV` | CV Parser → Planner, Matching, SkillGap, CoverLetter |
| `CVParseError` | CV Parser error branch |
| `SearchParams` | Planner → JobSearch |
| `JobPosting` | JobSearch → Matching |
| `ScoredPosting` | Matching → SkillGap / HumanSelect |
| `SkillGapResult` | SkillGap → HumanSelect |
| `HumanSelection` | HumanSelect → CoverLetter |
| `CoverLetterResult` | CoverLetter → END |
| `LLMNormalizeOutput` | LLM output schema for CV Parser LLM call |
| `LLMAdjustmentOutput` | LLM output schema for Matching LLM call |
| `LLMSkillGapOutput` | LLM output schema for SkillGap LLM call |
| `LLMCoverLetterOutput` | LLM output schema for CoverLetter LLM call |

---

### [NEW] `job_finder_agent/nodes/cv_parser.py`

**Python part (deterministic):**
- `pypdf` (or `pdfminer.six`) extracts raw text from the uploaded PDF bytes
- Employment date ranges parsed with `dateutil.parser`; `years_experience` computed in Python; `null` if no parseable dates found
- Edge cases handled: no text layer → structured `CVParseError`; corrupted/password-protected → caught exception → structured error; never raises uncaught

**LLM part (one call):**
- `LlmAgent(model=MODEL_NAME, output_schema=LLMNormalizeOutput)` called inline via `await ctx.run_node(llm_normalize_agent, ...)`
- Instruction: "Return ONLY valid JSON. Normalize skill names to canonical form, deduplicate, produce a 2-3 sentence English summary."
- Python deduplicates the returned skills list after the call (set-based)
- `raw_text` is **never** forwarded past this node (business rule)

**Output:** `ParsedCV` (or `CVParseError` on error path, routed to `"error"`)

---

### [NEW] `job_finder_agent/nodes/planner.py`

**Pure Python — zero LLM calls.**

Derives `SearchParams`:
- `target_titles`: takes first 2 past job titles from `parsed_cv.titles`; appends common variants
- `seniority`: inferred from `years_experience` bracket (0-2 junior, 3-6 mid, 7+ senior; null → omit)
- `location`: passes through `parsed_cv.location`; sets `is_remote=True` if location contains "remote" case-insensitively

---

### [NEW] `job_finder_agent/mcp_servers/jobspy_client.py`

Thin async wrapper that talks to the existing JobSpy MCP SSE server at `JOBSPY_SSE_URL`. Calls the `search_jobs` tool via HTTP POST and deserializes the JSON response into `list[JobPosting]`.

---

### [NEW] `job_finder_agent/nodes/job_search.py`

Calls `jobspy_client.search()` with `SearchParams`. Normalizes raw JobSpy output to `list[JobPosting]` (title, company, location, description, url, posted_date, salary). `security_flag` hardcoded to `False` for every posting (security checkpoint deferred per spec). Handles empty result list gracefully.

---

### [NEW] `job_finder_agent/nodes/matching.py`

**The critical Python/LLM split node:**

1. **Python baseline (0–60 pts):** extract skill keywords from `job.description` using simple tokenization + intersection with `cv.skills`. `baseline = min(60, round(overlap_ratio * 60))`. Special cases:
   - `cv.skills` empty → `baseline = 0` (LLM adjustment still runs using titles/summary as fallback)
   - `job.description` empty/null → cap final score at 40, skip LLM, set fixed rationale
   - `job.security_flag = True` → skip LLM, use baseline only

2. **LLM adjustment (-10 to +40):** `LlmAgent(output_schema=LLMAdjustmentOutput)` called per posting. Returns `{"delta": int, "rationale": str}`. If parse fails → `delta = 0`, log `"scoring_llm_parse_error"`.

3. **Python clamps:** `score = max(0, min(100, baseline + delta))`; Python converts to `int`.

4. **Python ranking:** `sorted(scored, key=lambda s: (-s.score, -s.posted_date.timestamp()))` — deterministic, stable.

5. Passes **only top-N** (`TOP_N_POSTINGS`) to skill-gap.

---

### [NEW] `job_finder_agent/nodes/skill_gap.py`

Runs over `top_n` postings only. For each posting: one `LlmAgent` call → `LLMSkillGapOutput` with `matched_skills`, `missing_skills`, `learning_suggestion`. Collects all into `list[SkillGapResult]`.

---

### [NEW] `job_finder_agent/nodes/human_select.py`

**The `RequestInput` pause.** Uses generator pattern:

```python
async def human_select(ctx: Context, node_input: list[ScoredPosting]):
    if not ctx.resume_inputs:
        # First pass: show ranked list + skill gaps → pause
        yield Event(content=..., ...)   # render to UI
        yield RequestInput(interrupt_id="job_selection", message=formatted_list)
        return
    # Resume: parse selection
    chosen_index = int(ctx.resume_inputs["job_selection"])
    yield Event(output=HumanSelection(posting=..., skill_gap=...))
```

`rerun_on_resume=False` (FunctionNode default) means the user's reply becomes the node output directly after yield/return — this is the correct ADK 2.0 pattern.

---

### [NEW] `job_finder_agent/nodes/cover_letter.py`

Runs only for the **single** selected posting:
- `security_flag = True` → return immediately with `flagged_for_review=True, draft=None` (no LLM)
- LLM call → `LLMCoverLetterOutput`
- Python word-count check: `len(draft.split())`
- If > `COVER_LETTER_MAX_WORDS`: **one retry** with shorter-length instruction appended
- If retry still over: return as-is with `long_draft=True` warning (no infinite loop)
- If 0 matched_skills: instruct LLM to focus on transferable experience, not fabricate matches

---

### [NEW] `job_finder_agent/agent.py`

```python
root_agent = Workflow(
    name="job_finder",
    edges=[
        ('START',        cv_parser_node),
        (cv_parser_node, planner_node,      "ok"),
        (cv_parser_node, error_handler,     "error"),
        (planner_node,   job_search_node),
        (job_search_node, matching_node),
        (matching_node,  skill_gap_node),
        (skill_gap_node, human_select_node),
        (human_select_node, cover_letter_node),
    ],
)
```

---

### [NEW] `job_finder_agent/__init__.py`

```python
from . import agent
```

---

## Open Questions

> [!IMPORTANT]
> **Python environment**: The project currently has no `pyproject.toml` / `requirements.txt` for the Python agent. I'll create a `pyproject.toml` (or `requirements.txt`) under `job_finder_agent/`. Should this use `uv` / `pip` / Poetry? I'll default to a plain `requirements.txt` unless you say otherwise.

> [!IMPORTANT]
> **PDF input transport**: `START` receives the user message as `types.Content`. For a file upload, the PDF bytes would need to arrive as a `Part` with inline bytes or a file URI. I'll wire the CV parser to extract bytes from `node_input.parts[0].inline_data.data` (base64). Let me know if your UI delivers PDFs differently.

> [!IMPORTANT]
> **JobSpy MCP connection mode**: The existing server supports both stdio and SSE. For the ADK workflow I'll call it via SSE HTTP (`http://localhost:9423`) with `httpx`. If you prefer stdio subprocess or the ADK built-in MCP tool client instead, let me know.

> [!IMPORTANT]
> **LLM calls per matching posting**: With default 20 JobSpy results, the Matching node makes up to 20 individual LLM calls (one per posting). This is correct per spec but can be slow. I can batch them with a single call if you prefer — the spec doesn't prohibit it. Default: one-per-posting as specified.

---

## Verification Plan

### Automated tests (after build)
- `pytest job_finder_agent/tests/` — unit tests for each node with mocked LLM/MCP
- Smoke test the full graph with `InMemoryRunner` and a sample PDF fixture

### Manual verification
- Start JobSpy MCP server (`npm start` in `jobspy-mcp-server/`)
- Run `adk web` or `agents-cli run job_finder_agent` and upload a sample PDF CV
- Confirm RequestInput pause shows the ranked list, then resume with a selection
- Confirm cover letter draft is returned with word count 250-400
