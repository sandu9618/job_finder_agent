"""
jobspy_client.py — async wrapper around the JobSpy MCP server.

Transports (config.JOBSPY_TRANSPORT):
  "sse"   — HTTP POST to JOBSPY_SSE_URL/api (server must run with ENABLE_SSE=1)
  "stdio" — spawn the MCP server subprocess and call the search_jobs tool
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from datetime import timedelta
from typing import Any, Optional

import httpx

from ..config import (
    JOBSPY_HOURS_OLD,
    JOBSPY_RESULTS_WANTED,
    JOBSPY_SITE_NAMES,
    JOBSPY_SSE_URL,
    JOBSPY_STDIO_ARGS,
    JOBSPY_STDIO_COMMAND,
    JOBSPY_STDIO_CWD,
    JOBSPY_TRANSPORT,
)
from ..schemas import JobPosting, SearchParams

logger = logging.getLogger(__name__)

# Job search can be slow (Docker + scrapers); allow up to 3 minutes over stdio.
_STDIO_TOOL_TIMEOUT = timedelta(seconds=180)


# ---------------------------------------------------------------------------
# Transport helpers
# ---------------------------------------------------------------------------

def _snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:])


def _to_mcp_arguments(params: dict[str, Any]) -> dict[str, Any]:
    """JobSpy MCP tool schema uses camelCase argument names."""
    return {_snake_to_camel(key): value for key, value in params.items()}


def _extract_jobs_payload(data: Any) -> list[dict[str, Any]]:
    """Normalize SSE / MCP response shapes to a list of raw job dicts."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("jobs", "data", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
    logger.warning("Unexpected JobSpy response shape: %s", type(data))
    return []


def _unwrap_exception(exc: BaseException) -> BaseException:
    """Return the innermost cause from nested ExceptionGroups."""
    current: BaseException = exc
    while True:
        if getattr(current, "exceptions", None):
            current = current.exceptions[0]  # type: ignore[attr-defined]
            continue
        nested = current.__cause__ or current.__context__
        if nested is None:
            return current
        current = nested


def _parse_mcp_tool_result(result: Any) -> list[dict[str, Any]]:
    """Parse a CallToolResult from the MCP search_jobs tool."""
    if getattr(result, "isError", False):
        message = getattr(result, "content", None) or result
        raise RuntimeError(f"JobSpy MCP tool error: {message}")

    text_chunks: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            text_chunks.append(text)

    if not text_chunks:
        return []

    payload = json.loads(text_chunks[0])
    return _extract_jobs_payload(payload)


async def _call_sse(params: dict[str, Any]) -> list[dict[str, Any]]:
    """POST to the JobSpy SSE server's /api endpoint and return raw job list."""
    payload = {
        "method": "search_jobs",
        "params": params,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{JOBSPY_SSE_URL}/api", json=payload)
        resp.raise_for_status()
        data = resp.json()

    return _extract_jobs_payload(data)


async def _call_stdio(params: dict[str, Any]) -> list[dict[str, Any]]:
    """Spawn the JobSpy MCP server on stdio and call search_jobs."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    env["ENABLE_SSE"] = "0"

    server = StdioServerParameters(
        command=JOBSPY_STDIO_COMMAND,
        args=JOBSPY_STDIO_ARGS,
        cwd=JOBSPY_STDIO_CWD,
        env=env,
    )

    logger.info(
        "Starting JobSpy MCP stdio: %s %s (cwd=%s)",
        JOBSPY_STDIO_COMMAND,
        " ".join(JOBSPY_STDIO_ARGS),
        JOBSPY_STDIO_CWD,
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_jobs",
                arguments=_to_mcp_arguments(params),
                read_timeout_seconds=_STDIO_TOOL_TIMEOUT,
            )
            return _parse_mcp_tool_result(result)


async def _dispatch(params: dict[str, Any]) -> list[dict[str, Any]]:
    if JOBSPY_TRANSPORT == "sse":
        return await _call_sse(params)
    if JOBSPY_TRANSPORT == "stdio":
        return await _call_stdio(params)
    raise RuntimeError(
        f"Unsupported JOBSPY_TRANSPORT={JOBSPY_TRANSPORT!r}; use 'sse' or 'stdio'."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _parse_date(raw: Any) -> Optional[date]:
    """Leniently parse a date from JobSpy's raw output."""
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(raw), fmt).date()
        except ValueError:
            continue
    return None


def _normalize_posting(raw: dict[str, Any], idx: int) -> JobPosting:
    """Map a raw JobSpy dict to the JobPosting schema."""
    url = str(raw.get("job_url") or raw.get("jobUrl") or raw.get("url") or "")
    job_id = raw.get("id") or raw.get("job_id") or raw.get("jobId") or (
        url.split("/")[-1] if url else f"job_{idx}"
    )

    return JobPosting(
        job_id=str(job_id)[:64],
        title=str(raw.get("title") or ""),
        company=str(raw.get("company") or raw.get("company_name") or raw.get("companyName") or ""),
        location=str(raw.get("location") or ""),
        description=str(raw.get("description") or ""),
        url=url,
        posted_date=_parse_date(
            raw.get("date_posted") or raw.get("datePosted") or raw.get("posted_date")
        ),
        salary=str(raw.get("min_amount") or raw.get("minAmount") or raw.get("salary") or "")
        or None,
        security_flag=False,
    )


async def search(params: SearchParams) -> list[JobPosting]:
    """
    Call the JobSpy MCP server and return normalized postings.

    Raises RuntimeError on network/server errors — let the job_search node
    handle this and return an empty list gracefully.
    """
    raw_params: dict[str, Any] = {
        "search_term": params.search_term,
        "results_wanted": params.results_wanted,
        "hours_old": params.hours_old,
        "site_names": params.site_names,
        "format": "json",
    }
    if params.location:
        raw_params["location"] = params.location
    if params.country_indeed:
        raw_params["country_indeed"] = params.country_indeed
    if params.is_remote:
        raw_params["is_remote"] = True

    logger.info("Calling JobSpy search (%s): %s", JOBSPY_TRANSPORT, raw_params)
    try:
        raw_jobs = await _dispatch(raw_params)
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"JobSpy server returned {exc.response.status_code}") from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Could not reach JobSpy server: {exc}") from exc
    except Exception as exc:
        root = _unwrap_exception(exc)
        if root is not exc:
            raise RuntimeError(f"JobSpy search failed: {root}") from exc
        raise RuntimeError(f"JobSpy search failed: {exc}") from exc

    postings = [_normalize_posting(job, i) for i, job in enumerate(raw_jobs)]
    logger.info("JobSpy returned %d postings", len(postings))
    return postings
