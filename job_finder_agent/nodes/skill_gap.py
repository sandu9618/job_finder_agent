"""
skill_gap.py — Skill Gap node (Node 5 in the graph).

Runs on the top-N ranked postings only (bounded by matching node).
Makes ONE LLM call per posting (spec requirement) to identify:
  • matched_skills   — skills the candidate has that the posting requires
  • missing_skills   — skills the posting requires that the candidate lacks
  • learning_suggestion — 1-2 sentence actionable bridge suggestion

Reads parsed_cv from graph state (set by cv_parser_node).
Outputs a RankedJobList combining scored postings + skill gaps + CV ref,
ready for the RequestInput (human selection) node.
"""

from __future__ import annotations

import json
import logging

from google.adk.agents import Context, LlmAgent
from google.adk.workflow import node
from google.genai import types

from ..config import MODEL_NAME, TOP_N_POSTINGS
from ..schemas import (
    LLMSkillGapOutput,
    ParsedCV,
    RankedJobList,
    ScoredPosting,
    SkillGapResult,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LLM agent — one call per posting
# ─────────────────────────────────────────────────────────────────────────────

_skill_gap_llm_agent = LlmAgent(
    name="skill_gap_analyzer",
    model=MODEL_NAME,
    instruction=(
        "You are a career skills analyst. Given a candidate profile and a single job posting, "
        "identify the skill gaps.\n\n"
        "Return ONLY valid JSON matching the output schema:\n"
        "  matched_skills: skills from the candidate's profile that this job explicitly requires.\n"
        "  missing_skills: skills the job requires that the candidate has NOT listed — "
        "infer from the description, not just the title.\n"
        "  learning_suggestion: 1-2 concise, actionable sentences for bridging the most "
        "critical missing skill. If there are no missing skills, suggest a way to highlight "
        "a strength instead.\n\n"
        "Do NOT fabricate skills not present in either the profile or the posting."
    ),
    output_schema=LLMSkillGapOutput,
    output_key="skill_gap_out",
)


# ─────────────────────────────────────────────────────────────────────────────
# Graph node
# ─────────────────────────────────────────────────────────────────────────────

@node(rerun_on_resume=True)
async def skill_gap_node(
    ctx: Context,
    node_input: list,    # list[ScoredPosting dict] from matching_node
    parsed_cv: dict,     # from ctx.state["parsed_cv"]
):
    """
    Skill Gap node — one LLM call per top-N posting.

    Input:  list of ScoredPosting dicts (node_input) + ParsedCV dict (state)
    Output: RankedJobList dict (postings + skill gaps + cv)
    """
    # ── Deserialize ───────────────────────────────────────────────────────
    try:
        cv = ParsedCV(**parsed_cv)
    except Exception as exc:
        logger.error("skill_gap_node: cannot parse CV from state: %s", exc)
        cv = ParsedCV()

    scored_postings: list[ScoredPosting] = []
    for raw in node_input or []:
        try:
            scored_postings.append(ScoredPosting(**raw))
        except Exception as exc:
            logger.warning("Skipping malformed ScoredPosting: %s", exc)

    # ── One LLM call per posting ──────────────────────────────────────────
    skill_gaps: list[SkillGapResult] = []

    candidate_snippet = {
        "skills": cv.skills,
        "titles": cv.titles,
        "summary": cv.summary,
        "years_experience": cv.years_experience,
    }

    # Limit to top-N postings
    scored_postings = scored_postings[:TOP_N_POSTINGS]

    for sp in scored_postings:
        if sp.posting.security_flag:
            skill_gaps.append(
                SkillGapResult(
                    job_id=sp.posting.job_id,
                    matched_skills=None,
                    missing_skills=None,
                    learning_suggestion="Skill-gap analysis skipped because this posting was flagged by the security checkpoint."
                )
            )
            continue

        posting_snippet = {
            "title": sp.posting.title,
            "company": sp.posting.company,
            "description": (sp.posting.description or "")[:2_000],
        }
        prompt_text = json.dumps(
            {"candidate": candidate_snippet, "posting": posting_snippet},
            ensure_ascii=False,
        )
        llm_input = types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt_text)],
        )
        try:
            llm_result = await ctx.run_node(_skill_gap_llm_agent, node_input=llm_input)
            gap_out = LLMSkillGapOutput(**(llm_result or {}))
        except Exception as exc:
            logger.error(
                "skill_gap LLM call failed for job_id=%s: %s", sp.posting.job_id, exc
            )
            # Graceful fallback — reuse Python-computed lists from matching node.
            gap_out = LLMSkillGapOutput(
                matched_skills=sp.matched_skills,
                missing_skills=sp.missing_skills,
                learning_suggestion="Could not generate learning suggestion.",
            )

        if not cv.skills:
            gap_out.learning_suggestion = (gap_out.learning_suggestion + " (Note: Skill data was limited from CV.)").strip()

        skill_gaps.append(
            SkillGapResult(
                job_id=sp.posting.job_id,
                matched_skills=gap_out.matched_skills,
                missing_skills=gap_out.missing_skills,
                learning_suggestion=gap_out.learning_suggestion,
            )
        )

    ranked = RankedJobList(cv=cv, postings=scored_postings, skill_gaps=skill_gaps)
    return ranked.model_dump(mode="json")
