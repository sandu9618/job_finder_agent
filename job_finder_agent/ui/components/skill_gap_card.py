import streamlit as st
from job_finder_agent.schemas import ScoredPosting, SkillGapResult


def _score_badge_html(score: int) -> str:
    if score >= 75:
        return '<span class="score-badge strong">Strong fit</span>'
    if score >= 50:
        return '<span class="score-badge good">Good fit</span>'
    return '<span class="score-badge stretch">Stretch role</span>'


def _skill_chips(skills: list[str], kind: str) -> str:
    if not skills:
        return ""
    chips = "".join(f'<span class="skill-chip {kind}">{s}</span>' for s in skills)
    return chips


def render_skill_gap_card(sp: ScoredPosting, gap: SkillGapResult, index: int):
    """Render a single job posting card with match info, gaps, and an action button."""
    p = sp.posting

    with st.container(border=True):
        header_l, header_r = st.columns([4, 1])
        with header_l:
            if p.security_flag:
                st.warning("Flagged for manual review", icon="⚠️")
            st.markdown(f"#### {index}. {p.title}")
            st.caption(f"{p.company} · {p.location}")
        with header_r:
            st.metric("Match", f"{sp.score}")
            st.markdown(_score_badge_html(sp.score), unsafe_allow_html=True)

        st.markdown(f"[View original posting]({p.url})")

        with st.expander("Why this score?", expanded=sp.score >= 60):
            st.markdown(sp.rationale)
            if gap.matched_skills:
                st.markdown("**Matched skills**")
                st.markdown(_skill_chips(gap.matched_skills, "match"), unsafe_allow_html=True)
            if gap.missing_skills:
                st.markdown("**Gaps**")
                st.markdown(_skill_chips(gap.missing_skills, "gap"), unsafe_allow_html=True)
            if gap.learning_suggestion:
                st.info(gap.learning_suggestion)

        disabled = st.session_state.is_processing or st.session_state.selected_job_id is not None
        if st.button(
            "Draft cover letter",
            key=f"btn_draft_{p.job_id}",
            disabled=disabled,
            type="primary",
            use_container_width=True,
        ):
            st.session_state.selected_job_id = p.job_id
            st.rerun()
