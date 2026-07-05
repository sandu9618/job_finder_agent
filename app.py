import asyncio
from pathlib import Path

from dotenv import load_dotenv

# Load API keys from repo-root .env before ADK / Gemini clients initialize.
load_dotenv(Path(__file__).resolve().parent / ".env")

import streamlit as st

from job_finder_agent.ui.state import init_state, build_resume_message, USER_ID, node_name_from_event, reset_downstream_state
from job_finder_agent.ui.components.cv_upload import render_cv_upload
from job_finder_agent.ui.components.job_list import render_job_list
from job_finder_agent.ui.components.cover_letter import render_cover_letter
from job_finder_agent.ui.styles import (
    inject_global_styles,
    render_app_header,
    render_hero,
    render_sidebar_config,
    render_stepper,
)

from job_finder_agent import config

if config.UI_HIDE_STREAMLIT_CHROME:
    st.set_option("client.toolbarMode", "minimal")

st.set_page_config(
    page_title="CareerPilot",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_styles(hide_streamlit_chrome=config.UI_HIDE_STREAMLIT_CHROME)
init_state()

with st.sidebar:
    render_sidebar_config(config)

_HERO_COPY = {
    "upload": (
        "Find your next role",
        "Upload a CV to parse skills, search live listings, score matches, and draft a cover letter.",
    ),
    "results": (
        "Your matched roles",
        "Compare scores and skill gaps, then pick one posting to generate a tailored cover letter.",
    ),
    "generating": (
        "Writing your cover letter",
        "The agent is drafting from your CV and the job you selected.",
    ),
    "draft": (
        "Review your draft",
        "Edit the letter below, then copy it when you are ready to apply.",
    ),
}


async def resume_graph(job_id: str):
    st.session_state.is_processing = True
    runner = st.session_state.runner
    session_id = st.session_state.session_id
    interrupt_id = st.session_state.pending_interrupt_id or "job_selection_0"
    resume_message = build_resume_message(interrupt_id, job_id)

    with st.spinner("Generating cover letter…"):
        try:
            last_output = None
            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session_id,
                new_message=resume_message,
            ):
                output = getattr(event, "output", None)
                if output is not None:
                    last_output = output
                if node_name_from_event(event) == "cover_letter_node" and output is not None:
                    last_output = output

            st.session_state.cover_letter_result = last_output
        except Exception as e:
            st.error(f"Error resuming workflow: {e}")

    st.session_state.is_processing = False
    st.rerun()


render_app_header()

if st.session_state.cover_letter_result:
    title, subtitle = _HERO_COPY["draft"]
    render_hero(title, subtitle)
    render_stepper()

    job_title = "Selected Job"
    if st.session_state.ranked_jobs:
        for p in st.session_state.ranked_jobs.get("postings", []):
            if p.get("posting", {}).get("job_id") == st.session_state.selected_job_id:
                job_title = p["posting"]["title"]
                break

    render_cover_letter(st.session_state.cover_letter_result, job_title)

elif st.session_state.selected_job_id:
    title, subtitle = _HERO_COPY["generating"]
    render_hero(title, subtitle)
    render_stepper()
    with st.status("Running cover letter node…", expanded=True):
        asyncio.run(resume_graph(st.session_state.selected_job_id))

elif st.session_state.ranked_jobs:
    title, subtitle = _HERO_COPY["results"]
    render_hero(title, subtitle)
    render_stepper()

    toolbar_l, toolbar_r = st.columns([3, 1])
    with toolbar_r:
        if st.button("Upload new CV", type="secondary", use_container_width=True):
            reset_downstream_state()
            st.rerun()

    render_job_list(st.session_state.ranked_jobs)

else:
    title, subtitle = _HERO_COPY["upload"]
    render_hero(title, subtitle)
    render_stepper()
    render_cv_upload()
