# ---------------------------------------------------------------------------
# config.py — single source of truth for all tunables in the graph.
# Change values here; nothing else needs to be edited for threshold changes.
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_REPO_ROOT / ".env")
_JOBSPY_SERVER_DIR = _REPO_ROOT / "jobspy-mcp-server"
_JOBSPY_SERVER_SCRIPT = _JOBSPY_SERVER_DIR / "src" / "index.js"

# ── Model ──────────────────────────────────────────────────────────────────
# The only model used anywhere in the graph. Override via MODEL_NAME in .env.
MODEL_NAME: str = os.environ.get("MODEL_NAME", "gemini-2.5-flash")

# ── Matching / Scoring ──────────────────────────────────────────────────────
# Maximum points the Python skill-overlap baseline can award (spec: 0-60).
SKILL_BASELINE_MAX: int = 60

# LLM adjustment delta bounds (spec: -10 to +40).
LLM_DELTA_MIN: int = -10
LLM_DELTA_MAX: int = 40

# Final score clamp (spec: 0-100 integer).
SCORE_MIN: int = 0
SCORE_MAX: int = 100

# ── Skill Gap ───────────────────────────────────────────────────────────────
# Only the top-N scored postings are passed to the skill-gap node.
# Bounds the number of LLM calls made in that node.
TOP_N_POSTINGS: int = 10

# ── Cover Letter ────────────────────────────────────────────────────────────
COVER_LETTER_MIN_WORDS: int = 250
COVER_LETTER_MAX_WORDS: int = 400

# ── JobSpy MCP Server ───────────────────────────────────────────────────────
# Transport: "sse" POSTs to a running HTTP server at JOBSPY_SSE_URL (default).
#            "stdio" spawns the MCP server as a subprocess (no HTTP server).
JOBSPY_TRANSPORT: str = os.environ.get("JOBSPY_TRANSPORT", "sse")

# SSE mode — requires `ENABLE_SSE=1 npm start` in jobspy-mcp-server.
JOBSPY_SSE_URL: str = os.environ.get("JOBSPY_SSE_URL", "http://localhost:9423")

# Stdio mode — spawns node with the JobSpy MCP entry script.
JOBSPY_STDIO_COMMAND: str = os.environ.get("JOBSPY_STDIO_COMMAND", "node")
JOBSPY_STDIO_ARGS: list[str] = os.environ.get(
    "JOBSPY_STDIO_ARGS", str(_JOBSPY_SERVER_SCRIPT)
).split()
JOBSPY_STDIO_CWD: str = os.environ.get(
    "JOBSPY_STDIO_CWD", str(_JOBSPY_SERVER_DIR)
)

# Default search parameters forwarded to JobSpy.
JOBSPY_RESULTS_WANTED: int = 20
JOBSPY_HOURS_OLD: int = 72
JOBSPY_SITE_NAMES: str = "indeed,linkedin,glassdoor"

# ── Streamlit UI ────────────────────────────────────────────────────────────
# Set UI_HIDE_STREAMLIT_CHROME=1 (or true) to hide the top toolbar/header for demos.
UI_HIDE_STREAMLIT_CHROME: bool = os.environ.get(
    "UI_HIDE_STREAMLIT_CHROME", ""
).lower() in ("1", "true", "yes")
