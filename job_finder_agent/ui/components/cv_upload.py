import asyncio

import streamlit as st
from google.genai import types

from job_finder_agent.schemas import ParsedCV
from job_finder_agent import config
from ..state import (
    USER_ID,
    reset_downstream_state,
    node_name_from_event,
    sync_session_state,
)


def _pdf_content(pdf_bytes: bytes) -> types.Content:
    """Wrap uploaded PDF bytes in the Content shape cv_parser_node expects."""
    return types.Content(
        role="user",
        parts=[types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")],
    )


async def run_graph_to_pause(runner, session_id: str, pdf_bytes: bytes):
    """Run the ADK graph from CV parsing until it pauses at RequestInput."""
    status_box = st.status("Running job-finder workflow…", expanded=True)
    status_text = status_box.empty()
    progress_bar = st.progress(0, text="Starting…")

    node_stages = {
        "cv_parser_node": ("Parsing CV…", 10),
        "planner_node": ("Planning job search…", 30),
        "job_search_node": ("Searching job boards…", 50),
        "security_checkpoint": ("Security checkpoint…", 65),
        "matching_node": ("Scoring and ranking…", 80),
        "skill_gap_node": ("Analyzing skill gaps…", 95),
        "human_select_node": ("Ready for your review.", 100),
    }

    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=_pdf_content(pdf_bytes),
        ):
            node_name = node_name_from_event(event)
            if node_name:
                stage_info = node_stages.get(node_name)
                if stage_info:
                    status_text.markdown(f"**{stage_info[0]}**")
                    progress_bar.progress(stage_info[1], text=stage_info[0])

            output = getattr(event, "output", None)
            if isinstance(output, dict) and "postings" in output:
                st.session_state.ranked_jobs = output

            from google.adk.workflow.utils._workflow_hitl_utils import (
                get_request_input_interrupt_ids,
                has_request_input_function_call,
            )

            if has_request_input_function_call(event):
                interrupt_ids = get_request_input_interrupt_ids(event)
                if interrupt_ids:
                    st.session_state.pending_interrupt_id = interrupt_ids[0]
                status_text.markdown("**Workflow paused — pick a job to continue.**")
                progress_bar.progress(100, text="Ready for review")

        await sync_session_state(runner, session_id)

        if not st.session_state.ranked_jobs or not st.session_state.ranked_jobs.get(
            "postings"
        ):
            status_box.update(label="No jobs found", state="error", expanded=True)
            if config.JOBSPY_TRANSPORT == "sse":
                hint = (
                    f"Start the JobSpy MCP server with SSE at `{config.JOBSPY_SSE_URL}` "
                    "(run `ENABLE_SSE=1 npm start` in jobspy-mcp-server/), then try again."
                )
            else:
                hint = (
                    "JobSpy stdio search returned no postings. Ensure Node.js is installed, "
                    "run `npm install` in jobspy-mcp-server/, and that Docker + the `jobspy` "
                    "image are available for scraping."
                )
            st.error(f"No job postings were returned. {hint}")
        else:
            count = len(st.session_state.ranked_jobs["postings"])
            status_box.update(label=f"Found {count} matched jobs", state="complete", expanded=False)

    except Exception as e:
        status_box.update(label="Workflow failed", state="error", expanded=True)
        st.error(f"Error executing workflow: {e}")
        status_text.markdown("Execution failed.")


def render_cv_upload():
    """Render the PDF upload screen and profile summary."""
    left, right = st.columns([1.1, 0.9], gap="large")

    with left:
        with st.container(border=True):
            st.subheader("Upload your CV")
            st.caption("One PDF at a time · max 10 MB · text-based resumes work best")

            uploaded_file = st.file_uploader(
                "Choose a resume file",
                type=["pdf"],
                accept_multiple_files=False,
                label_visibility="collapsed",
                disabled=st.session_state.is_processing,
                key=f"cv_pdf_uploader_{st.session_state.cv_uploader_key}",
            )

            if isinstance(uploaded_file, list):
                st.error("Please upload only one CV at a time.")
                return

            if uploaded_file is not None:
                if uploaded_file.size > 10 * 1024 * 1024:
                    st.error("File exceeds the 10 MB limit.")
                    return

                meta_l, meta_r = st.columns(2)
                meta_l.metric(
                    "File",
                    uploaded_file.name[:28] + ("…" if len(uploaded_file.name) > 28 else ""),
                )
                meta_r.metric("Size", f"{uploaded_file.size / 1024:.0f} KB")

                if st.button("Find matching jobs", type="primary", use_container_width=True):
                    st.session_state.is_processing = True
                    reset_downstream_state()
                    pdf_bytes = uploaded_file.getvalue()
                    asyncio.run(
                        run_graph_to_pause(
                            st.session_state.runner,
                            st.session_state.session_id,
                            pdf_bytes,
                        )
                    )
                    st.session_state.is_processing = False
                    st.rerun()

    with right:
        st.markdown(
            """
            <div class="info-panel">
              <h4>What happens next</h4>
              <ol>
                <li><strong>Parse</strong> your CV for skills, titles, and experience</li>
                <li><strong>Search</strong> Indeed and LinkedIn via JobSpy</li>
                <li><strong>Score</strong> each posting with Python + Gemini</li>
                <li><strong>Analyze</strong> skill gaps on the top matches</li>
                <li><strong>Pause</strong> so you can pick a role and draft a cover letter</li>
              </ol>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.parsed_cv:
            try:
                cv_obj = ParsedCV(**st.session_state.parsed_cv)
                st.success("CV parsed successfully")
                st.markdown(f"**Recent titles:** {', '.join(cv_obj.titles[:3]) or '—'}")
                st.markdown(f"**Skills detected:** {len(cv_obj.skills)}")
                exp = cv_obj.years_experience
                verified = "verified" if cv_obj.years_experience_verified else "estimated"
                st.markdown(f"**Experience:** {exp} yrs ({verified})" if exp else "**Experience:** not detected")
            except Exception:
                pass
