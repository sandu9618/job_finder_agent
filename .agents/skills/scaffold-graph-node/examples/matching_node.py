"""
matching.py — Matching & Scoring node (Node 4 in the graph).

This is the most important Python/LLM split in the graph.

───────────────────────────────────────────────────────────────────────────
PYTHON owns:                    │ LLM owns:
─────────────────────────────── │ ───────────────────────────────────────
Skill-overlap baseline (0-60)   │ Adjustment delta (-10 to +40)
Arithmetic (baseline + delta)   │ Rationale string
Clamp to 0-100                  │ (ONE batched call for ALL postings)
Final score as int              │
Sorting / ranking               │
Tie-breaking by posted_date     │
───────────────────────────────────────────────────────────────────────────

Batching strategy:
  All postings are bundled into a single LLM call.  The LLM returns an
  adjustment delta + rationale per posting.  Python maps results back by
  job_id.  If a posting is missing from the LLM response, delta defaults
  to 0.  If the entire call fails, all deltas default to 0 (baseline-only).

Edge cases (per spec):
  • security_flag=True  → skip LLM, baseline-only score, fixed rationale.
  • empty description   → cap final score at 40, skip LLM, fixed rationale.
  • cv.skills empty     → baseline = 0, LLM still runs on titles/summary.
  • LLM parse error     → delta = 0, log "scoring_llm_parse_error".
  • two postings tie    → stable tie-break by posted_date descending.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Optional

from google.adk.agents import Context, LlmAgent
from google.adk.workflow import node
from google.genai import types

from ..config import (
    LLM_DELTA_MAX,
    LLM_DELTA_MIN,
    MODEL_NAME,
    SCORE_MAX,
    SCORE_MIN,
    SKILL_BASELINE_MAX,
    TOP_N_POSTINGS,
)
from ..schemas import (
    JobPosting,
    LLMAdjustmentBatchOutput,
    LLMAdjustmentItem,
    ParsedCV,
    ScoredPosting,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LLM agent — one batched call for ALL postings
# ─────────────────────────────────────────────────────────────────────────────

_matching_llm_agent = LlmAgent(
    name="matching_adjuster",
    model=MODEL_NAME,
    instruction=(
        "You are a job-matching specialist. You receive a candidate profile and a list "
        "of job postings (as JSON). For EACH posting, return a judgment adjustment:\n\n"
        "  delta: integer in [-10, +40] representing the adjustment to add to the posting's "
        "Python-computed baseline skill-overlap score (0-60).\n"
        "  rationale: 1-3 sentences citing specific seniority fit, role-title alignment, "
        "or description nuance.\n\n"
        "Scoring guidance:\n"
        "  • Strong seniority + title fit + domain match → delta near +40\n"
        "  • Good fit but minor mismatch → delta +10 to +25\n"
        "  • Neutral / unclear → delta 0\n"
        "  • Seniority mismatch or role pivot → delta -5 to -10\n\n"
        "Return ONLY valid JSON matching the output schema. "
        "Include ALL job_ids from the input — no omissions. "
        "If a posting description is empty, return delta=0."
    ),
    output_schema=LLMAdjustmentBatchOutput,
    output_key="matching_adjustments",
)

# ─────────────────────────────────────────────────────────────────────────────
# Pure-Python helpers
# ─────────────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens from text, length >= 2, basic stop-word removal."""
    stop = {"the", "and", "for", "with", "that", "this", "you", "are", "our", "your"}
    return {
        w.lower().strip(".,;:'\"()")
        for w in text.split()
        if len(w) >= 2 and w.lower() not in stop
    }


def _compute_baseline(cv_skills: list[str], posting: JobPosting) -> tuple[int, list[str], list[str]]:
    """
    Python skill-overlap baseline: 0–SKILL_BASELINE_MAX points.

    Returns:
        baseline_score, matched_skills, missing_skills
    """
    if not cv_skills:
        return 0, [], []

    cv_tokens = {s.lower().strip() for s in cv_skills if s.strip()}
    desc_tokens = _tokenize(posting.description + " " + posting.title)

    matched = [s for s in cv_skills if s.lower().strip() in desc_tokens]
    missing = [s for s in cv_skills if s.lower().strip() not in desc_tokens]

    if not cv_tokens:
        return 0, [], []

    overlap_ratio = len(matched) / len(cv_tokens)
    score = min(SKILL_BASELINE_MAX, round(overlap_ratio * SKILL_BASELINE_MAX))
    return score, matched, missing


def _posting_date_ts(p: JobPosting) -> float:
    """Unix timestamp of posted_date for tie-breaking (descending = more recent first)."""
    if p.posted_date is None:
        return 0.0
    if isinstance(p.posted_date, datetime):
        return p.posted_date.timestamp()
    # date object
    return datetime(p.posted_date.year, p.posted_date.month, p.posted_date.day).timestamp()


def _clamp(score: int) -> int:
    return max(SCORE_MIN, min(SCORE_MAX, score))


def _build_batch_prompt(cv: ParsedCV, postings: list[JobPosting]) -> str:
    """Serialize candidate + postings into the LLM input string."""
    candidate = {
        "skills": cv.skills,
        "titles": cv.titles,
        "years_experience": cv.years_experience,
        "years_experience_verified": cv.years_experience_verified,
        "summary": cv.summary,
    }
    posting_list = [
        {
            "job_id": p.job_id,
            "title": p.title,
            "company": p.company,
            "location": p.location,
            # Truncate description to ~1 000 chars per posting to control token usage.
            "description_excerpt": (p.description or "")[:1_000],
        }
        for p in postings
    ]
    return json.dumps({"candidate": candidate, "postings": posting_list}, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────────────────────
# Graph node
# ─────────────────────────────────────────────────────────────────────────────

@node(rerun_on_resume=True)
async def matching_node(
    ctx: Context,
    node_input: list,          # list[JobPosting dict] from job_search_node
    parsed_cv: dict,           # read from ctx.state["parsed_cv"]
):
    """
    Matching node — hybrid Python baseline + batched LLM delta.

    Input:  list of JobPosting dicts (node_input) + ParsedCV dict (state)
    Output: list of top-N ScoredPosting dicts, ranked by score desc
    """
    # ── 0. Deserialize inputs ─────────────────────────────────────────────
    try:
        cv = ParsedCV(**parsed_cv)
    except Exception as exc:
        logger.error("matching_node: cannot parse CV from state: %s", exc)
        cv = ParsedCV()

    postings: list[JobPosting] = []
    for raw in node_input or []:
        try:
            postings.append(JobPosting(**raw))
        except Exception as exc:
            logger.warning("Skipping malformed posting: %s", exc)

    if not postings:
        logger.warning("matching_node: no postings to score — returning empty list")
        return []

    # ── 1. Python: compute baselines for all postings ─────────────────────
    # Separate flagged/empty-description postings — they never hit the LLM.
    flagged: list[JobPosting] = []
    no_desc: list[JobPosting] = []
    normal: list[JobPosting] = []

    for p in postings:
        if p.security_flag:
            flagged.append(p)
        elif not (p.description or "").strip():
            no_desc.append(p)
        else:
            normal.append(p)

    # Compute baselines for ALL postings now.
    baselines: dict[str, tuple[int, list[str], list[str]]] = {}
    for p in postings:
        baselines[p.job_id] = _compute_baseline(cv.skills, p)

    # ── 2. LLM: one batched call for eligible postings ────────────────────
    # "Eligible" = normal postings (not flagged, not empty-description).
    llm_adjustments: dict[str, LLMAdjustmentItem] = {}

    if normal:
        batch_prompt = _build_batch_prompt(cv, normal)
        llm_input = types.Content(
            role="user",
            parts=[types.Part.from_text(text=batch_prompt)],
        )
        try:
            llm_result = await ctx.run_node(_matching_llm_agent, node_input=llm_input)
            batch_out = LLMAdjustmentBatchOutput(**(llm_result or {}))
            for item in batch_out.adjustments:
                # Clamp delta to spec bounds in Python — never trust raw LLM value.
                clamped_delta = max(LLM_DELTA_MIN, min(LLM_DELTA_MAX, item.delta))
                llm_adjustments[item.job_id] = LLMAdjustmentItem(
                    job_id=item.job_id,
                    delta=clamped_delta,
                    rationale=item.rationale,
                )
        except Exception as exc:
            logger.error("scoring_llm_parse_error: %s", exc)
            # All deltas default to 0 — baseline-only scores for this run.
            for p in normal:
                llm_adjustments[p.job_id] = LLMAdjustmentItem(
                    job_id=p.job_id, delta=0,
                    rationale="Score based on keyword match only; LLM adjustment unavailable.",
                )

    # ── 3. Python: assemble final scores ──────────────────────────────────
    scored: list[ScoredPosting] = []

    for p in postings:
        baseline, matched, missing = baselines[p.job_id]

        if p.security_flag:
            # Spec: skip LLM, baseline-only, fixed rationale.
            score = _clamp(baseline)
            rationale = (
                "Score based on keyword match only; "
                "posting flagged for manual review."
            )
        elif not (p.description or "").strip():
            # Spec: cap at 40 regardless of title match.
            score = min(40, _clamp(baseline))
            rationale = "Insufficient posting detail to score confidently."
        else:
            adj = llm_adjustments.get(p.job_id)
            delta = adj.delta if adj else 0
            rationale = adj.rationale if adj else "Score based on keyword match only."
            # Python owns the addition and the clamp — LLM never sees the final number.
            score = _clamp(baseline + delta)

        scored.append(
            ScoredPosting(
                posting=p,
                score=score,
                rationale=rationale,
                matched_skills=matched,
                missing_skills=missing,
            )
        )

    # ── 4. Python: rank descending by score, tie-break by posted_date desc ─
    scored.sort(key=lambda s: (-s.score, -_posting_date_ts(s.posting)))

    # ── 5. Return top-N only — bounds skill-gap LLM call volume ──────────
    top_n = scored[:TOP_N_POSTINGS]
    logger.info(
        "Matching: scored %d postings, returning top %d (scores: %s)",
        len(scored),
        len(top_n),
        [s.score for s in top_n],
    )

    return [s.model_dump(mode="json") for s in top_n]
