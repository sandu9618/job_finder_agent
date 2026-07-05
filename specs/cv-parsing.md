# Spec: CV Parsing

## Purpose
Convert an uploaded PDF CV into structured data the rest of the graph can use:
skills, experience, titles, seniority signal, education, location preference.

## Requirements

### Input
- A single PDF file, uploaded by the user, max 10MB.
- CV may be 1-10 pages, any layout (single column, two column, with sidebar).

### Output (structured object)
```
{
  "raw_text": str,
  "skills": [str],          # normalized, deduplicated
  "titles": [str],          # past job titles, most recent first
  "years_experience": float,
  "education": [str],
  "location": str | null,
  "summary": str            # 2-3 sentence LLM-generated profile summary
}
```

### Processing rule
- Text extraction (PDF → text) is deterministic, done in Python, no LLM.
- Skill normalization (e.g. "React.js" / "ReactJS" / "React" → "React") uses a
  single LLM call over the extracted text, constrained to return JSON only.
- Years of experience is computed in Python from parsed employment date ranges,
  not estimated by the LLM, unless dates are missing or unparseable.

## Architecture
- Deterministic extraction and date-math live in Python.
- The LLM is used only for skill normalization and the summary — both are
  judgment/normalization tasks, not arithmetic or control flow.

## Edge Cases

```gherkin
Scenario: Scanned/image-only PDF with no extractable text
  Given the uploaded PDF contains no machine-readable text layer
  When CV parsing runs
  Then the node returns an error result with reason "no_text_layer"
  And the user is prompted to upload a text-based PDF instead
  And no LLM call is made

Scenario: CV has no clear employment dates
  Given the parsed text has job titles but no parseable date ranges
  When computing years_experience
  Then years_experience is set to null
  And the field is flagged as "unverified" in the output
  And downstream scoring treats years_experience as unknown, not zero

Scenario: Skill normalization produces a duplicate
  Given the raw text contains "React" and "React.js" as separate mentions
  When the LLM normalization step runs
  Then the output skills list contains "React" exactly once

Scenario: CV is in a language other than English
  Given the extracted text is not in English
  When CV parsing runs
  Then the node still extracts skills using the LLM step (multilingual capable)
  But the summary is generated in English
  And the original raw_text is preserved unmodified

Scenario: PDF parsing throws an exception
  Given the PDF is corrupted or password protected
  When extraction is attempted
  Then the node catches the exception
  And returns a structured error, never raises uncaught into the graph
```

## Business Rules
- Never send the full raw CV text to the job-search or scoring nodes — only the
  structured fields. Raw text stays scoped to the parsing node and the
  skill-gap node where it's explicitly needed.
- The LLM call for normalization must be given a closed instruction ("return
  only valid JSON matching this schema") — no open-ended generation here.