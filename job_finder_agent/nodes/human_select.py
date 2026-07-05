"""
human_select.py — Human-in-the-Loop selection node (Node 6 in the graph).

This is the RequestInput pause point.  The graph suspends here, shows the
ranked job list with scores and skill gaps to the user, and waits for them
to pick exactly one posting by number.

How the ADK 2.0 HITL pattern works here
─────────────────────────────────────────
1. First invocation (ctx.resume_inputs is empty):
   • Emit a content event so the web UI renders the ranked list.
   • yield RequestInput(interrupt_id="job_selection_<attempt>", ...)
   • return — graph suspends (persists state to session storage).

2. On resume (user submitted a reply):
   • Framework reruns this node with ctx.resume_inputs populated.
   • Node checks ctx.resume_inputs for the interrupt_id.
   • If found and valid → yield HumanSelection dict.
   • If invalid (bad number) → increment attempt counter, yield another
     RequestInput with a new interrupt_id (unique per retry per spec note).

The node is declared @node(rerun_on_resume=True) so the framework reruns
it (with ctx.resume_inputs) rather than treating the raw reply as the output.
"""

from __future__ import annotations

import logging

from google.adk.agents import Context
from google.adk.events import RequestInput
from google.adk.workflow import node
from google.genai import types

from ..schemas import (
    HumanSelection,
    ParsedCV,
    RankedJobList,
    ScoredPosting,
    SkillGapResult,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Display formatting
# ─────────────────────────────────────────────────────────────────────────────

def _format_ranked_list(ranked: RankedJobList) -> str:
    """Build the human-readable ranked job list for the UI content event."""
    lines: list[str] = [
        "## 🎯 Your Matched Jobs",
        f"Found **{len(ranked.postings)}** postings ranked by match score.\n",
    ]

    gap_by_id = {g.job_id: g for g in ranked.skill_gaps}

    for i, sp in enumerate(ranked.postings, start=1):
        p = sp.posting
        gap = gap_by_id.get(p.job_id, SkillGapResult(job_id=p.job_id))

        date_str = f"Posted {p.posted_date}" if p.posted_date else "Date unknown"
        salary_str = f" · {p.salary}" if p.salary else ""

        flagged_note = " ⚠️ **FLAGGED FOR MANUAL REVIEW**" if p.security_flag else ""
        lines.append(f"### ID: {p.job_id} — {p.title} @ {p.company}{flagged_note}")
        lines.append(f"📍 {p.location}  |  🏆 Score: **{sp.score}/100**  |  📅 {date_str}{salary_str}")
        lines.append(f"🔗 {p.url}")
        lines.append(f"\n> {sp.rationale}")

        if gap.matched_skills:
            lines.append(f"\n✅ **Matched skills:** {', '.join(gap.matched_skills)}")
        if gap.missing_skills:
            lines.append(f"❌ **Missing skills:** {', '.join(gap.missing_skills)}")
        if gap.learning_suggestion:
            lines.append(f"📚 **Learning tip:** {gap.learning_suggestion}")
        lines.append("")  # blank line between entries

    lines.append("---")
    lines.append("Enter the **job_id** of the job you'd like to apply for.")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Graph node
# ─────────────────────────────────────────────────────────────────────────────

@node(rerun_on_resume=True)
async def human_select_node(ctx: Context, node_input: dict):
    """
    RequestInput node — pauses the graph for human job selection.

    Input:  RankedJobList dict (from skill_gap_node)
    Output: HumanSelection dict (forwarded to cover_letter_node)

    State read:   ctx.state.get("select_attempt", 0)  — retry counter
    State written: {"select_attempt": <n>}
    """
    # ── Deserialize ───────────────────────────────────────────────────────
    try:
        ranked = RankedJobList(**node_input)
    except Exception as exc:
        logger.error("human_select_node: invalid RankedJobList: %s", exc)
        # Cannot proceed without the ranked list.
        yield types.Content(
            role="model",
            parts=[types.Part.from_text(text="⚠️ An error occurred loading the job list. Please restart.")],
        )
        return

    # ── Determine which attempt we're on ──────────────────────────────────
    attempt: int = ctx.state.get("select_attempt", 0)
    interrupt_id = f"job_selection_{attempt}"

    # ── Check if we have a reply for this attempt ─────────────────────────
    if interrupt_id not in (ctx.resume_inputs or {}):
        # First pass (or new retry) — show the list and pause.
        display_text = _format_ranked_list(ranked)

        ctx.state["select_attempt"] = attempt
        yield types.Content(
            role="model",
            parts=[types.Part.from_text(text=display_text)],
        )
        yield RequestInput(
            interrupt_id=interrupt_id,
            message="Enter the job_id of the job you want to apply for:",
        )
        return

    # ── We have a reply — validate it ─────────────────────────────────────
    raw_reply = str(ctx.resume_inputs[interrupt_id]).strip()
    
    selected_sp = next((sp for sp in ranked.postings if sp.posting.job_id == raw_reply), None)

    if not selected_sp:
        # Invalid input — increment attempt, ask again with a new interrupt_id.
        new_attempt = attempt + 1
        new_interrupt_id = f"job_selection_{new_attempt}"
        error_msg = (
            f"⚠️ '{raw_reply}' is not a valid selection. "
            f"Please enter an exact job_id from the list."
        )
        ctx.state["select_attempt"] = new_attempt
        yield types.Content(
            role="model",
            parts=[types.Part.from_text(text=error_msg)],
        )
        yield RequestInput(
            interrupt_id=new_interrupt_id,
            message="Enter an exact job_id from the list:",
        )
        return

    # ── Valid selection — resume the graph ────────────────────────────────
    gap = next(
        (g for g in ranked.skill_gaps if g.job_id == selected_sp.posting.job_id),
        SkillGapResult(job_id=selected_sp.posting.job_id),
    )

    logger.info(
        "User selected job_id %s: %s @ %s (score=%d)",
        selected_sp.posting.job_id,
        selected_sp.posting.title,
        selected_sp.posting.company,
        selected_sp.score,
    )

    selection = HumanSelection(
        cv=ranked.cv,
        posting=selected_sp.posting,
        score=selected_sp.score,
        skill_gap=gap,
    )

    # Emit a confirmation to the UI before handing off to cover-letter.
    confirmation = (
        f"✅ Got it! Generating a cover letter for **{selected_sp.posting.title}** "
        f"at **{selected_sp.posting.company}** (score: {selected_sp.score}/100)…"
    )
    yield types.Content(
        role="model",
        parts=[types.Part.from_text(text=confirmation)],
    )
    yield selection.model_dump(mode="json")
