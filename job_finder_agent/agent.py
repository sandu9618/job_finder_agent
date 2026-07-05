"""
agent.py — ADK 2.0 Workflow graph definition for the job-finder agent.

Graph topology (sequential with one error branch):

    START
      │
      ▼
  cv_parser_node ──"error"──► error_handler_node (terminal)
      │ "ok"
      ▼
  planner_node  (pure Python)
      │
      ▼
  job_search_node  (calls JobSpy MCP)
      │
      ▼
  security_checkpoint  (PII redaction + prompt-injection heuristics, fail-closed)
      │
      ▼
  matching_node  (Python baseline + batched LLM delta + Python rank)
      │
      ▼
  skill_gap_node  (one LLM call per top-N posting)
      │
      ▼
  human_select_node  ◄──── RequestInput HITL pause (graph suspends here)
      │  (resumes when user picks a posting)
      ▼
  cover_letter_node  (single-posting LLM draft + Python word-count)
      │
      ▼
    END

State flow:
  ctx.state["parsed_cv"]  — written by cv_parser_node, refreshed by planner_node
                             read by matching_node and skill_gap_node
  ctx.state["raw_text"]   — written by cv_parser_node
                             (currently not read downstream; reserved for skill_gap
                              if deep-text analysis is needed later)
  ctx.state["select_attempt"] — retry counter managed by human_select_node
"""

from google.adk.workflow import Workflow

from .nodes.cover_letter import cover_letter_node
from .nodes.cv_parser import cv_parser_node
from .nodes.error_handler import error_handler_node
from .nodes.human_select import human_select_node
from .nodes.job_search import job_search_node
from .nodes.matching import matching_node
from .nodes.planner import planner_node
from .nodes.security_checkpoint import security_checkpoint
from .nodes.skill_gap import skill_gap_node

root_agent = Workflow(
    name="job_finder",
    description=(
        "An ADK 2.0 graph workflow that parses a CV, searches for matching jobs, "
        "scores and ranks them, asks the user to pick one, then generates a tailored "
        "cover letter."
    ),
    edges=[
        # Entry
        ("START",          cv_parser_node),

        # Conditional branch for cv_parser_node
        (cv_parser_node,   {"ok": planner_node, "error": error_handler_node}),

        # Happy path
        (planner_node,     job_search_node),
        (job_search_node,  security_checkpoint),
        (security_checkpoint, matching_node),
        (matching_node,    skill_gap_node),
        (skill_gap_node,   human_select_node),
        (human_select_node, cover_letter_node),
    ],
)
