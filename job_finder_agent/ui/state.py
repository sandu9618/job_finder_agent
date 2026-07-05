"""Streamlit session helpers for running the job-finder ADK workflow."""

from __future__ import annotations

import uuid

import streamlit as st
from google.adk.runners import InMemoryRunner
from google.genai import types

from job_finder_agent.agent import root_agent

APP_NAME = "job_finder"
USER_ID = "streamlit-user"


def create_runner() -> InMemoryRunner:
    """Create an in-memory ADK runner with session auto-creation enabled."""
    runner = InMemoryRunner(node=root_agent, app_name=APP_NAME)
    runner.auto_create_session = True
    return runner


def new_session_id() -> str:
    return f"streamlit-{uuid.uuid4().hex[:12]}"


def init_state() -> None:
    """Initialize all session state variables needed for the Job Finder UI."""
    if "runner" not in st.session_state:
        st.session_state.runner = create_runner()

    if "session_id" not in st.session_state:
        st.session_state.session_id = new_session_id()

    if "parsed_cv" not in st.session_state:
        st.session_state.parsed_cv = None

    if "ranked_jobs" not in st.session_state:
        st.session_state.ranked_jobs = None

    if "selected_job_id" not in st.session_state:
        st.session_state.selected_job_id = None

    if "cover_letter_result" not in st.session_state:
        st.session_state.cover_letter_result = None

    if "pending_interrupt_id" not in st.session_state:
        st.session_state.pending_interrupt_id = None

    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False

    if "cv_uploader_key" not in st.session_state:
        st.session_state.cv_uploader_key = 0

    # Legacy key from the pre-Runner UI — drop if present.
    st.session_state.pop("agent_context", None)


def reset_downstream_state() -> None:
    """Clear results from a previous CV run and start a fresh ADK session."""
    st.session_state.parsed_cv = None
    st.session_state.ranked_jobs = None
    st.session_state.selected_job_id = None
    st.session_state.cover_letter_result = None
    st.session_state.pending_interrupt_id = None
    st.session_state.session_id = new_session_id()
    st.session_state.cv_uploader_key += 1


def reset_selection() -> None:
    """Clear the selected job and draft, going back to the results list."""
    st.session_state.selected_job_id = None
    st.session_state.cover_letter_result = None


def build_resume_message(interrupt_id: str, value: str) -> types.Content:
    """Build the user message that resumes a paused RequestInput interrupt."""
    from google.adk.workflow.utils._workflow_hitl_utils import create_request_input_response

    return types.Content(
        role="user",
        parts=[
            create_request_input_response(
                interrupt_id,
                {"result": value},
            )
        ],
    )


async def sync_session_state(runner: InMemoryRunner, session_id: str) -> None:
    """Copy parsed_cv from the ADK session into Streamlit state."""
    session = await runner.session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
    )
    if session and session.state.get("parsed_cv"):
        st.session_state.parsed_cv = session.state["parsed_cv"]


def node_name_from_event(event) -> str | None:
    """Extract the graph node name from an ADK event, if present."""
    path = getattr(getattr(event, "node_info", None), "path", "") or ""
    if not path:
        return None
    segment = path.rsplit("/", 1)[-1]
    return segment.split("@", 1)[0] or None
