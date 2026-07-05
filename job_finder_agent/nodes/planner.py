"""
planner.py — Planner node (Node 2 in the graph).

Pure Python — zero LLM calls.

Derives JobSpy search parameters from the ParsedCV:
  • search_term   — first past job title (most recent), or a generic fallback
  • seniority     — inferred from years_experience bracket
  • location      — passed through from CV; "remote" detected case-insensitively
  • is_remote     — True if location string contains "remote"

The ParsedCV is passed as node_input (direct predecessor output from cv_parser).
The Planner also writes parsed_cv to state so downstream nodes (matching,
skill_gap) can read it by parameter name.
"""

from __future__ import annotations

import logging
from typing import Optional

from google.adk.agents import Context

from ..config import JOBSPY_HOURS_OLD, JOBSPY_RESULTS_WANTED, JOBSPY_SITE_NAMES
from ..schemas import ParsedCV, SearchParams

logger = logging.getLogger(__name__)

# Seniority bracket thresholds (years of experience)
_JUNIOR_MAX = 2.0
_MID_MAX = 6.0


def _infer_seniority(years: Optional[float]) -> Optional[str]:
    """Return 'junior' | 'mid' | 'senior' | None (when years_experience is null)."""
    if years is None:
        return None
    if years <= _JUNIOR_MAX:
        return "junior"
    if years <= _MID_MAX:
        return "mid"
    return "senior"


def _build_search_term(cv: ParsedCV) -> str:
    """
    Build the primary search term from the CV's most recent title.
    Falls back to a skills-based term if no titles were extracted.
    """
    if cv.titles:
        # Use the most recent title; strip seniority prefixes for broader results.
        title = cv.titles[0]
        for prefix in ("Senior", "Junior", "Lead", "Principal", "Staff", "Head of"):
            title = title.replace(prefix, "").strip()
        return title or cv.titles[0]

    if cv.skills:
        # Take top 2 skills as a fallback search term.
        return " ".join(cv.skills[:2])

    return "software engineer"  # ultimate fallback


def _is_remote(location: Optional[str]) -> bool:
    if not location:
        return False
    return "remote" in location.lower()


def _infer_country_indeed(location: Optional[str]) -> Optional[str]:
    """Map CV location hints to JobSpy country_indeed values."""
    if not location:
        return None
    loc = location.lower()
    if "sri lanka" in loc:
        return "sri lanka"
    return None


def planner_node(ctx: Context, node_input: dict):
    """
    Planner node — pure Python, no LLM.

    Input:  ParsedCV dict (from cv_parser_node via node_input)
    Output: SearchParams dict
    State:  Writes parsed_cv so matching + skill_gap can read it.
    """
    try:
        cv = ParsedCV(**node_input)
    except Exception as exc:
        logger.error("Planner could not parse CV input: %s", exc)
        # Fallback: use empty CV defaults so the graph continues.
        cv = ParsedCV()

    search_term = _build_search_term(cv)
    seniority = _infer_seniority(cv.years_experience if cv.years_experience_verified else None)
    is_remote = _is_remote(cv.location)
    location = cv.location if not is_remote else None  # remote → no city filter
    country_indeed = _infer_country_indeed(cv.location)

    params = SearchParams(
        search_term=search_term,
        location=location,
        is_remote=is_remote,
        seniority=seniority,
        results_wanted=JOBSPY_RESULTS_WANTED,
        hours_old=JOBSPY_HOURS_OLD,
        site_names=JOBSPY_SITE_NAMES,
        country_indeed=country_indeed,
    )

    logger.info(
        "Planner derived: term=%r, location=%r, remote=%s, seniority=%s",
        params.search_term,
        params.location,
        params.is_remote,
        params.seniority,
    )

    ctx.state["parsed_cv"] = cv.model_dump()
    return params.model_dump()
