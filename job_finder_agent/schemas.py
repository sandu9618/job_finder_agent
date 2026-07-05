# ---------------------------------------------------------------------------
# schemas.py — all Pydantic models used as node I/O boundaries.
# Every node validates its output against these models before passing data
# to the next node.  The LLM output_schema models are kept here too so
# they stay in sync with the node schemas they feed into.
# ---------------------------------------------------------------------------

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ═══════════════════════════════════════════════════════════════════════════
# Node 1: CV Parser
# ═══════════════════════════════════════════════════════════════════════════

class LLMNormalizeOutput(BaseModel):
    """Structured output from the CV normalization LLM call."""
    skills: list[str] = Field(
        default_factory=list,
        description="Canonical, normalized skill names; already deduplicated by the LLM.",
    )
    titles: list[str] = Field(
        default_factory=list,
        description="Past job titles extracted from the CV, most recent first.",
    )
    summary: str = Field(
        default="",
        description="2-3 sentence English professional summary.",
    )


class ParsedCV(BaseModel):
    """Structured output of the CV Parser node.  raw_text is NOT included here
    (it stays in graph state only, scoped to parsing and skill-gap nodes)."""
    skills: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list, description="Most recent first")
    years_experience: Optional[float] = Field(
        default=None,
        description="Python-computed from employment date ranges; null if dates missing.",
    )
    years_experience_verified: bool = Field(
        default=False,
        description="False means dates were absent/unparseable; treat as unknown downstream.",
    )
    education: list[str] = Field(default_factory=list)
    location: Optional[str] = None
    summary: str = ""


class CVParseError(BaseModel):
    """Returned (via route='error') when CV parsing cannot proceed."""
    reason: str  # "no_text_layer" | "corrupted" | "parse_error" | "no_pdf"
    message: str


# ═══════════════════════════════════════════════════════════════════════════
# Node 2: Planner
# ═══════════════════════════════════════════════════════════════════════════

class SearchParams(BaseModel):
    """Parameters the Planner derives and forwards to the Job Search node."""
    search_term: str
    location: Optional[str] = None
    is_remote: bool = False
    seniority: Optional[str] = Field(
        default=None,
        description="'junior' | 'mid' | 'senior' — omitted when years_experience is null.",
    )
    results_wanted: int = 20
    hours_old: int = 72
    site_names: str = "indeed,linkedin"
    country_indeed: Optional[str] = Field(
        default=None,
        description="Indeed/Glassdoor country filter (e.g. 'sri lanka', 'usa').",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Node 3: Job Search
# ═══════════════════════════════════════════════════════════════════════════

class JobPosting(BaseModel):
    """Normalized posting object; security_flag hardcoded False until checkpoint."""
    job_id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    posted_date: Optional[date] = None
    salary: Optional[str] = None
    security_flag: bool = False  # always False until security checkpoint is built


# ═══════════════════════════════════════════════════════════════════════════
# Node 4: Matching
# ═══════════════════════════════════════════════════════════════════════════

class LLMAdjustmentItem(BaseModel):
    """Per-posting adjustment from the batched matching LLM call."""
    job_id: str
    delta: int = Field(
        description="Integer adjustment in range [-10, +40].",
    )
    rationale: str = Field(
        description="1-3 sentences citing seniority fit, role alignment, nuance.",
    )


class LLMAdjustmentBatchOutput(BaseModel):
    """Output schema for the single batched matching LLM call."""
    adjustments: list[LLMAdjustmentItem]


class ScoredPosting(BaseModel):
    """A posting with its final score after Python baseline + LLM delta + clamp."""
    posting: JobPosting
    score: int = Field(description="0-100 integer, Python-owned arithmetic.")
    rationale: str
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# Node 5: Skill Gap
# ═══════════════════════════════════════════════════════════════════════════

class LLMSkillGapOutput(BaseModel):
    """Output schema for the per-posting skill-gap LLM call."""
    matched_skills: Optional[list[str]] = Field(default_factory=list)
    missing_skills: Optional[list[str]] = Field(default_factory=list)
    learning_suggestion: str = Field(
        default="",
        description="1-2 actionable sentences for bridging the most critical gap.",
    )


class SkillGapResult(BaseModel):
    """Skill-gap analysis result for one posting."""
    job_id: str
    matched_skills: Optional[list[str]] = Field(default_factory=list)
    missing_skills: Optional[list[str]] = Field(default_factory=list)
    learning_suggestion: str = ""


class RankedJobList(BaseModel):
    """Combined payload sent to the RequestInput node for human review."""
    cv: ParsedCV
    postings: list[ScoredPosting]   # ranked, top-N only
    skill_gaps: list[SkillGapResult]


# ═══════════════════════════════════════════════════════════════════════════
# Node 6: Human Select (RequestInput)
# ═══════════════════════════════════════════════════════════════════════════

class HumanSelection(BaseModel):
    """What the human picked — forwarded to cover-letter node."""
    cv: ParsedCV
    posting: JobPosting
    score: int
    skill_gap: SkillGapResult


# ═══════════════════════════════════════════════════════════════════════════
# Node 7: Cover Letter
# ═══════════════════════════════════════════════════════════════════════════

class LLMCoverLetterOutput(BaseModel):
    """Output schema for the cover letter LLM call."""
    draft: str


class CoverLetterResult(BaseModel):
    """Final output of the graph."""
    job_id: str
    draft: Optional[str] = None
    word_count: int = 0
    flagged_for_review: bool = False
    long_draft: bool = Field(
        default=False,
        description="True when the draft exceeded the word limit even after one retry.",
    )
