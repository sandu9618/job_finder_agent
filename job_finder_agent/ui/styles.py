"""Shared Streamlit styling and layout helpers."""

from __future__ import annotations

import streamlit as st


def inject_global_styles(*, hide_streamlit_chrome: bool = False) -> None:
    chrome_css = ""
    if hide_streamlit_chrome:
        chrome_css = """
          header[data-testid="stHeader"] {
            display: none !important;
          }
          [data-testid="stToolbar"] {
            display: none !important;
          }
          [data-testid="stDecoration"] {
            display: none !important;
          }
          [data-testid="stStatusWidget"] {
            display: none !important;
          }
          footer {
            display: none !important;
          }
          .block-container {
            padding-top: 1rem;
          }
        """

    st.markdown(
        """
        <style>
        """
        + chrome_css
        + """
          :root {
            --primary: #6366f1;
            --primary-dark: #4f46e5;
            --primary-light: #e0e7ff;
            --accent: #0d9488;
            --accent-light: #ccfbf1;
            --warm: #f59e0b;
            --warm-light: #fef3c7;
            --violet: #7c3aed;
            --rose: #e11d48;
            --slate-900: #0f172a;
            --slate-600: #475569;
            --slate-500: #64748b;
            --slate-200: #e2e8f0;
            --slate-100: #f1f5f9;
            --slate-50: #f8fafc;
          }

          .stApp {
            background: linear-gradient(180deg, #eef2ff 0%, var(--slate-50) 220px, #ffffff 100%);
          }

          .block-container {
            padding-top: 1.75rem;
            padding-bottom: 3rem;
            max-width: 1100px;
          }

          [data-testid="stSidebar"] {
            background: linear-gradient(165deg, #312e81 0%, #4338ca 42%, #4f46e5 100%);
            border-right: none;
          }
          [data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem;
          }
          [data-testid="stSidebar"] h1,
          [data-testid="stSidebar"] h2,
          [data-testid="stSidebar"] h3,
          [data-testid="stSidebar"] label,
          [data-testid="stSidebar"] p,
          [data-testid="stSidebar"] span,
          [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {
            color: #f8fafc !important;
          }
          [data-testid="stSidebar"] .stCaption,
          [data-testid="stSidebar"] small {
            color: #c7d2fe !important;
          }
          [data-testid="stSidebar"] hr {
            border-color: rgba(255, 255, 255, 0.2);
          }
          [data-testid="stSidebar"] div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.22);
            border-radius: 12px;
            padding: 0.65rem 0.85rem;
          }
          [data-testid="stSidebar"] div[data-testid="stMetric"] label,
          [data-testid="stSidebar"] div[data-testid="stMetric"] [data-testid="stMetricValue"] {
            color: #ffffff !important;
          }
          [data-testid="stSidebar"] [data-testid="stAlert"] {
            background: rgba(255, 255, 255, 0.14) !important;
            border: 1px solid rgba(255, 255, 255, 0.25) !important;
            color: #e0e7ff !important;
          }

          .app-brand {
            margin-bottom: 0.5rem;
            padding: 0.25rem 0 0.5rem 0;
          }
          .app-brand-badge {
            display: inline-block;
            background: linear-gradient(90deg, var(--primary) 0%, var(--violet) 100%);
            color: #fff;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            padding: 0.28rem 0.65rem;
            border-radius: 999px;
            margin-bottom: 0.65rem;
          }
          .app-brand h1 {
            margin: 0;
            font-size: 2.15rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            background: linear-gradient(90deg, #312e81 0%, var(--primary) 55%, var(--violet) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
          }
          .app-brand p {
            margin: 0.35rem 0 0 0;
            color: var(--slate-600);
            font-size: 1rem;
          }

          .app-hero {
            background: linear-gradient(125deg, #eef2ff 0%, #f5f3ff 45%, #ecfeff 100%);
            border: 1px solid #c7d2fe;
            border-left: 5px solid var(--primary);
            border-radius: 16px;
            padding: 1.5rem 1.75rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.08);
          }
          .app-hero h1 {
            margin: 0 0 0.35rem 0;
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--slate-900);
          }
          .app-hero p {
            margin: 0;
            color: var(--slate-600);
            font-size: 1rem;
          }

          .stepper {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin: 0.75rem 0 1.5rem 0;
          }
          .step-pill {
            padding: 0.4rem 0.9rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
            border: 1px solid var(--slate-200);
            background: #fff;
            color: var(--slate-500);
          }
          .step-pill.active {
            background: linear-gradient(90deg, var(--primary) 0%, #818cf8 100%);
            border-color: var(--primary-dark);
            color: #fff;
            box-shadow: 0 2px 8px rgba(99, 102, 241, 0.35);
          }
          .step-pill.done {
            background: var(--accent-light);
            border-color: #5eead4;
            color: #0f766e;
          }

          .config-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #c7d2fe !important;
            margin-bottom: 0.1rem;
          }
          .config-value {
            font-size: 0.95rem;
            color: #ffffff !important;
            font-weight: 600;
            margin-bottom: 0.85rem;
            padding: 0.35rem 0.55rem;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            border: 1px solid rgba(255, 255, 255, 0.15);
          }

          .sidebar-title {
            font-size: 1.35rem;
            font-weight: 800;
            color: #fff !important;
            margin: 0 0 0.15rem 0;
          }
          .sidebar-subtitle {
            color: #c7d2fe !important;
            font-size: 0.85rem;
            margin: 0 0 0.75rem 0;
          }

          div[data-testid="stMain"] div[data-testid="stMetric"] {
            background: #fff;
            border: 1px solid var(--slate-200);
            border-radius: 12px;
            padding: 0.65rem 0.85rem;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
          }
          div[data-testid="stMain"] div[data-testid="column"]:nth-child(1) div[data-testid="stMetric"] {
            border-top: 3px solid var(--primary);
          }
          div[data-testid="stMain"] div[data-testid="column"]:nth-child(2) div[data-testid="stMetric"] {
            border-top: 3px solid var(--accent);
          }
          div[data-testid="stMain"] div[data-testid="column"]:nth-child(3) div[data-testid="stMetric"] {
            border-top: 3px solid var(--warm);
          }
          div[data-testid="stMain"] div[data-testid="column"]:nth-child(4) div[data-testid="stMetric"] {
            border-top: 3px solid var(--violet);
          }

          div[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #c7d2fe !important;
            border-radius: 14px !important;
            background: #fff;
            box-shadow: 0 2px 12px rgba(99, 102, 241, 0.06);
          }

          .info-panel {
            background: linear-gradient(135deg, #f0fdfa 0%, #ecfeff 100%);
            border: 1px solid #99f6e4;
            border-radius: 14px;
            padding: 1.1rem 1.25rem;
            margin-top: 0.5rem;
          }
          .info-panel h4 {
            margin: 0 0 0.65rem 0;
            color: #0f766e;
            font-size: 0.95rem;
          }
          .info-panel ol {
            margin: 0;
            padding-left: 1.2rem;
            color: var(--slate-600);
            line-height: 1.65;
          }
          .info-panel li { margin-bottom: 0.35rem; }
          .info-panel strong { color: #115e59; }

          .score-badge {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 700;
            margin-top: 0.15rem;
          }
          .score-badge.strong {
            background: #d1fae5;
            color: #047857;
            border: 1px solid #6ee7b7;
          }
          .score-badge.good {
            background: #fef3c7;
            color: #b45309;
            border: 1px solid #fcd34d;
          }
          .score-badge.stretch {
            background: #ffe4e6;
            color: #be123c;
            border: 1px solid #fda4af;
          }

          .skill-chip {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            margin: 0.15rem 0.2rem 0.15rem 0;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
          }
          .skill-chip.match {
            background: #d1fae5;
            color: #065f46;
          }
          .skill-chip.gap {
            background: #fee2e2;
            color: #991b1b;
          }

          button[data-testid="baseButton-primary"] {
            background: linear-gradient(90deg, var(--primary-dark) 0%, var(--primary) 100%) !important;
            border: none !important;
            box-shadow: 0 2px 10px rgba(79, 70, 229, 0.3);
          }
          button[data-testid="baseButton-primary"]:hover {
            background: linear-gradient(90deg, #4338ca 0%, #6366f1 100%) !important;
            box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4);
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _current_step() -> int:
    if st.session_state.get("cover_letter_result"):
        return 4
    if st.session_state.get("selected_job_id"):
        return 3
    if st.session_state.get("ranked_jobs"):
        return 2
    return 1


def render_stepper() -> None:
    steps = [
        (1, "Upload CV"),
        (2, "Review matches"),
        (3, "Generate letter"),
        (4, "Edit draft"),
    ]
    current = _current_step()
    pills = []
    for num, label in steps:
        if num < current:
            cls = "step-pill done"
        elif num == current:
            cls = "step-pill active"
        else:
            cls = "step-pill"
        pills.append(f'<span class="{cls}">{num}. {label}</span>')
    st.markdown(f'<div class="stepper">{"".join(pills)}</div>', unsafe_allow_html=True)


def render_app_header() -> None:
    st.markdown(
        """
        <div class="app-brand">
          <h1>CareerPilot</h1>
          <p>Parse your CV, find matched roles, and draft tailored cover letters.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="app-hero">
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_config(config) -> None:
    st.markdown('<p class="sidebar-title">CareerPilot</p>', unsafe_allow_html=True)
    # st.markdown('<p class="sidebar-subtitle">ADK workflow app</p>', unsafe_allow_html=True)
    st.divider()
    st.markdown("### Configuration")
    st.caption("Runtime settings from `config.py`")

    st.markdown('<div class="config-label">Model</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="config-value">{config.MODEL_NAME}</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Top jobs", config.TOP_N_POSTINGS)
    with c2:
        st.metric("Max words", config.COVER_LETTER_MAX_WORDS)

    st.divider()
    st.info("Upload a PDF to run the full ADK workflow through matching and skill-gap analysis.")
