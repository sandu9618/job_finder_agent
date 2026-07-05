import streamlit as st
from job_finder_agent.schemas import RankedJobList, SkillGapResult
from .skill_gap_card import render_skill_gap_card


def render_job_list(ranked_jobs: dict):
    """Render the ranked job list."""
    try:
        ranked = RankedJobList(**ranked_jobs)
    except Exception as e:
        st.error(f"Error parsing job list: {e}")
        return

    if not ranked.postings:
        st.warning("No postings to show. Try uploading a different CV or broadening the search.")
        return

    flagged = sum(1 for sp in ranked.postings if sp.posting.security_flag)
    avg_score = round(sum(sp.score for sp in ranked.postings) / len(ranked.postings))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Matches", len(ranked.postings))
    m2.metric("Avg score", f"{avg_score}/100")
    m3.metric("Flagged", flagged)
    m4.metric("Skills in CV", len(ranked.cv.skills))

    st.markdown("---")

    gaps_by_id = {g.job_id: g for g in ranked.skill_gaps}

    for i, sp in enumerate(ranked.postings, start=1):
        gap = gaps_by_id.get(sp.posting.job_id) or SkillGapResult(job_id=sp.posting.job_id)
        render_skill_gap_card(sp, gap, i)
