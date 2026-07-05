"""
cover_letter.py — Cover Letter node (Node 7 / final in the graph).

Generates a single tailored cover letter for the ONE posting the human selected.
Never called for the full list — only fires after RequestInput confirmation.

Python responsibilities:
  • Word count check (len(draft.split())) — trusted over LLM's self-report
  • One retry if word count > COVER_LETTER_MAX_WORDS (spec: exactly one retry)
  • If retry still over limit → return draft as-is with long_draft=True warning
  • security_flag=True → no LLM call, return flagged_for_review=True, draft=None

LLM responsibility:
  • One call (or one retry) to write the 250-400 word cover letter draft.

Edge cases per spec:
  • security_flag=True  → flagged_for_review=True, draft=None, no LLM.
  • zero matched_skills → draft focuses on transferable experience, not fabricated.
  • draft > 400 words   → one retry with shorter-length instruction.
  • retry still over    → long_draft=True warning, return as-is.
"""

from __future__ import annotations

import logging

from google.adk.agents import Context, LlmAgent
from google.adk.workflow import node
from google.genai import types

from ..config import (
    COVER_LETTER_MAX_WORDS,
    COVER_LETTER_MIN_WORDS,
    MODEL_NAME,
)
from ..schemas import (
    CoverLetterResult,
    HumanSelection,
    LLMCoverLetterOutput,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# LLM agents — base call + retry variant (shorter-length instruction)
# ─────────────────────────────────────────────────────────────────────────────

_BASE_INSTRUCTION = """\
You are a professional cover letter writer. Write a tailored cover letter for the job application below.

Requirements:
- Target length: {min_words}–{max_words} words. This is CRITICAL — stay within this range.
- Reference at least 2 concrete skills or experiences from the candidate's profile that match the posting.
- Acknowledge at most 1 skill gap constructively (not apologetically). Frame it as a growth opportunity.
- If matched_skills is empty, focus on transferable experience and genuine interest — do NOT fabricate matches.
- Do NOT reference or attempt to reconstruct any redacted placeholders (e.g., [[EMAIL]], [[PHONE]]).
- State verified facts (verified skills, verified years_experience) confidently.
- State unverified facts tentatively (e.g., "approximately" for unverified years_experience).
- Professional tone, first person, no generic filler phrases ("I am writing to express...").
- Do NOT use the candidate's name if not provided.

Return ONLY valid JSON matching the output schema. The 'draft' field must be the full cover letter text.\
"""

_cover_letter_llm_agent = LlmAgent(
    name="cover_letter_writer",
    model=MODEL_NAME,
    instruction=_BASE_INSTRUCTION.format(
        min_words=COVER_LETTER_MIN_WORDS,
        max_words=COVER_LETTER_MAX_WORDS,
    ),
    output_schema=LLMCoverLetterOutput,
    output_key="cover_letter_out",
)

_cover_letter_retry_agent = LlmAgent(
    name="cover_letter_writer_retry",
    model=MODEL_NAME,
    instruction=(
        _BASE_INSTRUCTION.format(
            min_words=COVER_LETTER_MIN_WORDS,
            max_words=COVER_LETTER_MAX_WORDS,
        )
        + f"\n\nIMPORTANT: Your previous draft was too long. "
        f"You MUST keep the draft under {COVER_LETTER_MAX_WORDS} words. Be concise."
    ),
    output_schema=LLMCoverLetterOutput,
    output_key="cover_letter_retry_out",
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _word_count(text: str) -> int:
    """Python-owned word count. Never trust LLM's self-reported count."""
    return len(text.split())


def _build_prompt(selection: HumanSelection) -> str:
    """Serialize candidate + selected posting into the LLM input."""
    cv = selection.cv
    posting = selection.posting
    gap = selection.skill_gap

    lines = [
        "## Candidate Profile",
        f"Skills: {', '.join(cv.skills) or 'Not provided'}",
        f"Titles: {', '.join(cv.titles) or 'Not provided'}",
        (
            f"Years of Experience: {cv.years_experience} "
            f"({'verified' if cv.years_experience_verified else 'UNVERIFIED — do not state as certain'})"
            if cv.years_experience is not None
            else "Years of Experience: Unknown (do not state a figure)"
        ),
        f"Education: {', '.join(cv.education) or 'Not provided'}",
        f"Summary: {cv.summary or 'Not provided'}",
        "",
        "## Target Job Posting",
        f"Title: {posting.title}",
        f"Company: {posting.company}",
        f"Location: {posting.location}",
        f"Match Score: {selection.score}/100",
        f"Description:\n{(posting.description or '')[:3_000]}",
        "",
        "## Skill Gap Analysis",
        f"Matched Skills: {', '.join(gap.matched_skills) or 'None identified'}",
        f"Missing Skills: {', '.join(gap.missing_skills) or 'None identified'}",
        f"Learning Suggestion: {gap.learning_suggestion or 'N/A'}",
    ]
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Graph node
# ─────────────────────────────────────────────────────────────────────────────

@node(rerun_on_resume=True)
async def cover_letter_node(ctx: Context, node_input: dict):
    """
    Cover Letter node — generates one draft for the selected posting.

    Input:  HumanSelection dict (from human_select_node)
    Output: CoverLetterResult dict
    """
    # ── Deserialize ───────────────────────────────────────────────────────
    try:
        selection = HumanSelection(**node_input)
    except Exception as exc:
        logger.error("cover_letter_node: invalid HumanSelection: %s", exc)
        yield CoverLetterResult(
            job_id="unknown",
            draft=None,
            word_count=0,
            flagged_for_review=False,
            long_draft=False,
        ).model_dump()
        return

    posting = selection.posting

    # ── Edge case: security-flagged posting — no LLM call ─────────────────
    if posting.security_flag:
        logger.warning(
            "cover_letter_node: posting %s is security-flagged — skipping LLM", posting.job_id
        )
        yield types.Content(
            role="model",
            parts=[types.Part.from_text(
                text=(
                    "⚠️ This job posting was flagged for manual review. "
                    "An automated cover letter cannot be generated for it. "
                    "Please review the original listing manually before applying."
                )
            )],
        )
        yield CoverLetterResult(
            job_id=posting.job_id,
            draft=None,
            word_count=0,
            flagged_for_review=True,
        ).model_dump()
        return

    # ── Build the LLM input ───────────────────────────────────────────────
    prompt_text = _build_prompt(selection)
    llm_input = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt_text)],
    )

    # ── First LLM call ────────────────────────────────────────────────────
    draft: str = ""
    try:
        result = await ctx.run_node(_cover_letter_llm_agent, node_input=llm_input)
        draft = LLMCoverLetterOutput(**(result or {})).draft
    except Exception as exc:
        logger.error("cover_letter first LLM call failed: %s", exc)
        draft = ""

    # ── Python word-count check ───────────────────────────────────────────
    wc = _word_count(draft)
    long_draft = False

    if wc > COVER_LETTER_MAX_WORDS:
        logger.warning(
            "cover_letter_node: draft too long (%d words > %d) — attempting ONE retry",
            wc,
            COVER_LETTER_MAX_WORDS,
        )
        # ── One retry with explicit shorter-length instruction ─────────────
        retry_input = types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=prompt_text),
                types.Part.from_text(
                    text=f"\n\n[Previous draft was {wc} words — too long. Rewrite under {COVER_LETTER_MAX_WORDS} words.]"
                ),
            ],
        )
        try:
            retry_result = await ctx.run_node(_cover_letter_retry_agent, node_input=retry_input)
            retry_draft = LLMCoverLetterOutput(**(retry_result or {})).draft
            retry_wc = _word_count(retry_draft)
            if retry_wc <= COVER_LETTER_MAX_WORDS:
                draft = retry_draft
                wc = retry_wc
            else:
                # Spec: return as-is with long_draft warning — no infinite loop.
                logger.warning(
                    "cover_letter_node: retry still over limit (%d words) — returning with long_draft=True",
                    retry_wc,
                )
                draft = retry_draft
                wc = retry_wc
                long_draft = True
        except Exception as exc:
            logger.error("cover_letter retry LLM call failed: %s", exc)
            long_draft = True  # original draft retained

    # ── Emit final draft to UI ────────────────────────────────────────────
    if draft:
        ui_text = (
            f"## Cover Letter Draft\n"
            f"*{posting.title} @ {posting.company}*  |  {wc} words"
            + (" ⚠️ *Draft is longer than target — please edit before sending.*" if long_draft else "")
            + f"\n\n---\n\n{draft}"
        )
        yield types.Content(
            role="model",
            parts=[types.Part.from_text(text=ui_text)],
        )

    yield CoverLetterResult(
        job_id=posting.job_id,
        draft=draft or None,
        word_count=wc,
        flagged_for_review=posting.security_flag,
        long_draft=long_draft,
    ).model_dump()
