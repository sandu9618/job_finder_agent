"""
job_search.py — Job Search node (Node 3 in the graph).

Calls the JobSpy MCP server via jobspy_client.search() and returns a
normalized list of JobPosting objects.  Handles empty results and
network errors gracefully — never raises uncaught into the graph.

security_flag is hardcoded False on every posting (security checkpoint
is deferred per project spec).
"""

from __future__ import annotations

import logging

from google.adk.agents import Context
from google.genai import types

from ..mcp_servers import jobspy_client
from ..schemas import JobPosting, SearchParams

logger = logging.getLogger(__name__)


async def job_search_node(ctx: Context, node_input: dict):
    """
    Job Search node — calls JobSpy MCP, normalizes, and returns postings.

    Input:  SearchParams dict (from planner_node)
    Output: list of JobPosting dicts
    """
    try:
        params = SearchParams(**node_input)
    except Exception as exc:
        logger.error("job_search_node: invalid SearchParams input: %s", exc)
        # Return empty list — matching node handles empty gracefully.
        return []

    try:
        postings: list[JobPosting] = await jobspy_client.search(params)
    except RuntimeError as exc:
        logger.error("JobSpy search failed: %s", exc)
        postings = []

    if not postings:
        logger.warning("JobSpy returned 0 postings for search_term=%r", params.search_term)

    return [p.model_dump(mode="json") for p in postings]
