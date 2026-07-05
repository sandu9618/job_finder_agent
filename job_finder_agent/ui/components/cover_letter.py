import streamlit as st
from job_finder_agent.schemas import CoverLetterResult
from ..state import reset_selection


def render_cover_letter(result: dict, job_title: str):
    """Render the final cover letter draft or manual review message."""
    try:
        cl_result = CoverLetterResult(**result)
    except Exception as e:
        st.error(f"Error parsing cover letter result: {e}")
        return

    st.subheader(job_title)

    if cl_result.flagged_for_review:
        st.error(
            "This posting was flagged by the security checkpoint. "
            "An automated cover letter was not generated.",
            icon="⚠️",
        )
        st.info("Review the original listing manually before applying.")
    else:
        c1, c2 = st.columns(2)
        c1.metric("Word count", cl_result.word_count)
        c2.metric("Target range", "250–400 words")

        if cl_result.long_draft:
            st.warning("Draft exceeds the target length — consider trimming before sending.")

        draft_text = cl_result.draft or ""
        st.text_area(
            "Edit your cover letter",
            value=draft_text,
            height=420,
            help="Copy from here when you are ready to apply.",
        )

    st.divider()
    if st.button("← Back to job list", use_container_width=False):
        reset_selection()
        st.rerun()
