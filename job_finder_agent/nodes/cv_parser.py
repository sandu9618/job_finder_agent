"""
cv_parser.py — CV Parser node (Node 1 in the graph).

Python responsibilities (deterministic):
  • PDF text extraction via pypdf
  • Employment date parsing → years_experience (dateutil, not LLM)
  • Education and location heuristic extraction
  • Skill deduplication after LLM normalization

LLM responsibility (one call):
  • Skill normalization (React.js/ReactJS/React → React)
  • Past job title extraction
  • 2-3 sentence English summary

Error routing: sets ctx.route="error" and returns a CVParseError dict.
The graph's error edge routes that to error_handler_node.

Business rule: raw_text is stored in state only — it is NOT included in
the ParsedCV output model, keeping it scoped to this node and skill_gap.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from datetime import datetime
from typing import Optional

from google.adk.agents import Context, LlmAgent
from google.adk.workflow import node
from google.genai import types

from ..config import MODEL_NAME
from ..schemas import CVParseError, LLMNormalizeOutput, ParsedCV

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# LLM agent — skill normalization + title extraction + summary
# Defined at module level so the graph can introspect it if needed.
# ─────────────────────────────────────────────────────────────────────────────

_cv_normalize_agent = LlmAgent(
    name="cv_normalize",
    model=MODEL_NAME,
    instruction=(
        "You are a CV parser assistant. Given the raw text of a CV, perform THREE tasks:\n"
        "1. SKILLS: Extract all technical and professional skills mentioned. "
        "Normalize variants to canonical form (e.g. 'React.js', 'ReactJS', 'React' → 'React'). "
        "Return them deduplicated.\n"
        "2. TITLES: Extract past job titles, most recent first.\n"
        "3. SUMMARY: Write a 2-3 sentence English professional summary suitable for a recruiter. "
        "Use only facts present in the CV. The CV may be in any language; the summary must be English.\n\n"
        "Return ONLY valid JSON matching the output schema. "
        "Do NOT estimate years_experience — that is computed elsewhere. "
        "Do NOT invent any information not explicitly present in the CV text."
    ),
    output_schema=LLMNormalizeOutput,
    output_key="cv_normalize_out",
)


# ─────────────────────────────────────────────────────────────────────────────
# Pure-Python helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Deterministic PDF → plain text via pypdf (no LLM)."""
    import pypdf  # lazy import keeps startup fast if pypdf is optional

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    if reader.is_encrypted:
        raise ValueError("Password-protected PDF cannot be parsed.")
    pages: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages)


def _parse_years_experience(raw_text: str) -> tuple[Optional[float], bool]:
    """
    Parse employment date ranges from raw CV text.

    Returns:
        (years_experience, verified)
        years_experience — float or None if no parseable dates found.
        verified — False when dates were absent/unparseable (spec: treat as unknown).
    """
    from dateutil import parser as du_parser

    patterns = [
        # "Jan 2019 – Mar 2023" / "January 2019 - Present"
        r"([A-Za-z]+\.?\s+\d{4})\s*[–\-—]\s*([A-Za-z]+\.?\s+\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)",
        # "2019 – 2023" / "2021 – Present"
        r"\b(\d{4})\s*[–\-—]\s*(\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow)\b",
    ]

    now = datetime.now()
    total_days = 0
    found_any = False

    for pattern in patterns:
        for m in re.finditer(pattern, raw_text):
            start_str, end_str = m.group(1).strip(), m.group(2).strip()
            try:
                start_dt = du_parser.parse(start_str, default=datetime(now.year, 1, 1))
                if re.match(r"[Pp]resent|[Cc]urrent|[Nn]ow", end_str):
                    end_dt = now
                else:
                    end_dt = du_parser.parse(end_str, default=datetime(now.year, 12, 31))
                if start_dt < end_dt <= now:
                    total_days += (end_dt - start_dt).days
                    found_any = True
            except Exception:
                continue  # unparseable range — skip silently

    if not found_any:
        return None, False
    return round(total_days / 365.25, 1), True


def _extract_education(raw_text: str) -> list[str]:
    """Heuristic extraction of education entries from raw text."""
    edu_keywords = [
        "Bachelor", "Master", "PhD", "Ph.D", "B.Sc", "M.Sc", "B.Eng", "M.Eng",
        "BSc", "MSc", "MBA", "BEng", "MEng", "Diploma", "Associate", "Doctor",
        "B.A.", "M.A.", "BA ", "MA ", "LLB", "BEd", "MEd",
    ]
    edu_lines: list[str] = []
    seen: set[str] = set()
    for line in raw_text.splitlines():
        stripped = line.strip()
        if len(stripped) < 10:
            continue
        if any(kw.lower() in stripped.lower() for kw in edu_keywords):
            key = stripped[:80].lower()
            if key not in seen:
                seen.add(key)
                edu_lines.append(stripped)
    return edu_lines[:5]


def _extract_location_hint(raw_text: str) -> Optional[str]:
    """
    Best-effort extraction of location from the CV's header region (~500 chars).
    Returns city/state, country, or "Remote" / "Hybrid" if found.
    """
    header = raw_text[:500]
    # Match "City, ST" / "City, Country" / "Remote" / "Hybrid"
    m = re.search(
        r"\b([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)*,\s*(?:[A-Z]{2,3}|[A-Z][a-z]+))\b"
        r"|\b(Remote|Hybrid|On-site)\b",
        header,
    )
    return m.group(0) if m else None


def _dedup_skills(skills: list[str]) -> list[str]:
    """Case-insensitive deduplication preserving first occurrence order."""
    seen: set[str] = set()
    result: list[str] = []
    for s in skills:
        key = s.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(s.strip())
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Graph node
# ─────────────────────────────────────────────────────────────────────────────

@node(rerun_on_resume=True)
async def cv_parser_node(ctx: Context, node_input: types.Content):
    """
    CV Parser — first node in the graph.

    Input:  types.Content from START (PDF bytes as inline_data Part).
    Output: ParsedCV dict with ctx.route="ok"
         OR CVParseError dict with ctx.route="error"

    State written:
      ctx.state["parsed_cv"]  — ParsedCV dict (read by matching + skill_gap)
      ctx.state["raw_text"]   — plain text (read by skill_gap only)
    """
    def _parse_error(reason: str, message: str) -> dict:
        ctx.route = "error"
        return CVParseError(reason=reason, message=message).model_dump()
    # ── 1. Extract PDF bytes from the Content payload ─────────────────────
    pdf_bytes: Optional[bytes] = None
    raw_text: Optional[str] = None

    try:
        for part in node_input.parts or []:
            if hasattr(part, "inline_data") and part.inline_data:
                data = part.inline_data.data
                pdf_bytes = base64.b64decode(data) if isinstance(data, str) else bytes(data)
                break
        if pdf_bytes is None:
            # Fallback: accept raw text (useful for testing / text uploads).
            for part in node_input.parts or []:
                if hasattr(part, "text") and part.text:
                    raw_text = part.text
                    break
        if pdf_bytes is None and raw_text is None:
            return _parse_error(
                "no_pdf",
                "No PDF data found in the upload. Please attach a PDF file.",
            )
    except Exception as exc:
        logger.error("Error reading upload payload: %s", exc)
        return _parse_error("parse_error", str(exc))

    # ── 2. Extract text from PDF (deterministic, no LLM) ─────────────────
    if raw_text is None:
        try:
            raw_text = _extract_pdf_text(pdf_bytes)
        except ValueError as exc:
            # Password-protected or unreadable
            return _parse_error("corrupted", str(exc))
        except Exception as exc:
            logger.error("PDF extraction exception: %s", exc, exc_info=True)
            return _parse_error("parse_error", f"Failed to extract text from PDF: {exc}")

    if not raw_text.strip():
        return _parse_error(
            "no_text_layer",
            (
                "No machine-readable text found in the PDF. "
                "This appears to be a scanned/image-only document. "
                "Please upload a text-based PDF or run OCR first."
            ),
        )

    # ── 3. Python: compute years_experience from employment dates ─────────
    years_exp, exp_verified = _parse_years_experience(raw_text)

    # ── 4. Python: heuristic education + location extraction ──────────────
    education = _extract_education(raw_text)
    location_hint = _extract_location_hint(raw_text)

    # ── 5. LLM: skill normalization + title extraction + summary (1 call) ─
    # Truncate to ~8 000 chars to stay within token budget.
    llm_input = types.Content(
        role="user",
        parts=[types.Part.from_text(text=raw_text[:8_000])],
    )
    try:
        llm_result = await ctx.run_node(_cv_normalize_agent, node_input=llm_input)
        # run_node returns a dict when output_schema is set.
        normalize_out = LLMNormalizeOutput(**(llm_result or {}))
    except Exception as exc:
        logger.error("CV LLM normalization failed: %s", exc)
        # Graceful degradation — proceed with empty skills/titles.
        normalize_out = LLMNormalizeOutput(skills=[], titles=[], summary="")

    # ── 6. Python: deduplicate skills ─────────────────────────────────────
    skills = _dedup_skills(normalize_out.skills)

    parsed_cv = ParsedCV(
        skills=skills,
        titles=normalize_out.titles,
        years_experience=years_exp,
        years_experience_verified=exp_verified,
        education=education,
        location=location_hint,
        summary=normalize_out.summary,
    )

    ctx.state["parsed_cv"] = parsed_cv.model_dump()
    ctx.state["raw_text"] = raw_text
    ctx.route = "ok"
    return parsed_cv.model_dump()
