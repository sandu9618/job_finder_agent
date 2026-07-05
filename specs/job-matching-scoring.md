# Spec: Job Matching & Scoring

## Purpose
Given a parsed CV and a sanitized job posting (post-security-checkpoint only),
produce a 0-100 match score with a short rationale, ranked deterministically.

## Requirements

### Input
- Parsed CV object (see specs/cv_parsing.md)
- Sanitized job posting object: { title, company, location, description,
  url, posted_date, salary | null, security_flag: bool }

### Output (per posting)
```
{
  "job_id": str,
  "score": int,          # 0-100, integer
  "rationale": str,       # 1-3 sentences, cites specific overlaps/gaps
  "matched_skills": [str],
  "missing_skills": [str]
}
```

## Scoring Architecture
- Score computation is a **hybrid**, not a single LLM call:
  1. Python computes a baseline skill-overlap score (intersection of CV
     skills vs. skills extracted from the posting) — deterministic, 0-60 points.
  2. An LLM call adds a judgment adjustment of -10 to +40 points based on
     seniority fit, role-title alignment, and description nuance the
     keyword overlap can't capture.
  3. Python clamps the final sum to the 0-100 range and rounds to an integer.
- The LLM never outputs the final score alone — it outputs an adjustment delta
  and a rationale; Python owns the arithmetic and the clamp.
- Sorting/ranking of the job list is pure Python (sort by score descending,
  stable tie-break by posted_date descending).

## Edge Cases

```gherkin
Scenario: Posting flagged by the security checkpoint
  Given a job posting has security_flag = true (PII or injection detected)
  When the matching node processes it
  Then the LLM judgment step is skipped entirely
  And the score is set using the Python baseline-only calculation
  And the rationale states "Score based on keyword match only; posting
    flagged for manual review"

Scenario: CV has no skills extracted at all
  Given the parsed CV's skills list is empty
  When scoring any posting
  Then the baseline overlap score is 0
  And the LLM adjustment step still runs using titles/summary as fallback signal
  And the rationale notes "Limited skill data available from CV"

Scenario: Two postings tie on score
  Given two postings both score 78
  When the ranked list is produced
  Then the posting with the more recent posted_date appears first
  And both are shown to the user (no silent drop)

Scenario: LLM returns an out-of-range or non-numeric adjustment
  Given the LLM response for the adjustment delta fails schema validation
  When Python parses the response
  Then the adjustment defaults to 0
  And the event is logged as "scoring_llm_parse_error"
  And the baseline score alone is used, not blocked entirely

Scenario: Posting missing a description entirely
  Given a scraped posting has an empty or null description field
  When scoring runs
  Then the posting receives a maximum score of 40 regardless of title match
  And the rationale states "Insufficient posting detail to score confidently"
```

## Business Rules
- Only sanitized postings (post-security-checkpoint) ever reach the LLM
  adjustment step — no exceptions, including re-tries.
- Score and rationale are always returned together; never a bare number.
- The top-N (configurable, default 10) postings by score are the only ones
  passed to the skill-gap node, to bound LLM call volume.