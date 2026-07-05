# Spec: Cover Letter Drafting

## Purpose
Generate a tailored cover letter draft for exactly one job posting, only
after explicit human selection via the RequestInput step — never generated
in bulk for every matched job.

## Requirements

### Input
- Parsed CV object
- The single sanitized job posting the human selected
- The corresponding skill-gap result for that posting (see below)

### Output
```
{
  "job_id": str,
  "draft": str,       # full cover letter text
  "word_count": int,
  "flagged_for_review": bool   # true if source posting carried security_flag
}
```

### Trigger condition
- This node only runs after the RequestInput node receives an explicit job
  selection from the human. It never fires automatically for top-N matches.

### Generation rules
- Length target: 250-400 words, enforced by post-generation check in Python
  (word_count computed in code, not trusted from the LLM).
- Must reference at least 2 concrete skills/experiences from the CV that
  match the posting, and acknowledge at most 1 skill gap constructively
  (not apologetically).
- Must use the sanitized posting text only — if redacted_categories is
  non-empty, the letter must not attempt to "fill in" or guess the redacted
  values.

## Edge Cases

```gherkin
Scenario: User selects a job that was security-flagged
  Given the chosen posting has security_flag = true
  When the cover letter node is invoked
  Then the node does not call the LLM
  And instead returns flagged_for_review = true with draft = null
  And the UI tells the user this posting could not be auto-drafted and
    suggests reviewing the original listing manually before applying

Scenario: Generated draft exceeds the word count target
  Given the LLM returns a draft over 400 words
  When Python checks word_count
  Then the node makes one retry call with an explicit shorter-length
    instruction
  And if the retry still exceeds the limit, the draft is returned as-is with
    a "long_draft" warning flag rather than looping indefinitely

Scenario: CV has no matching skills for this specific posting
  Given the skill-gap result shows zero matched_skills for the selected job
  When drafting
  Then the node does not fabricate matches
  And the draft focuses on transferable experience and stated interest
    instead, and flags this honestly rather than inventing overlap

Scenario: User selects a job, then changes their mind before generation completes
  Given the human selection has been recorded
  When a new selection arrives before the draft is returned
  Then the in-flight generation for the prior selection is discarded
  And only the latest selection's draft is returned to the user

Scenario: Redacted placeholder appears in CV match context
  Given the posting description contains "[[EMAIL]]" from the security
    checkpoint
  When generating the draft
  Then the LLM is instructed never to reference or attempt to reconstruct
    redacted placeholders
  And the draft simply omits any reference to that field
```

## Business Rules
- One draft per human-confirmed selection. No batch generation.
- The LLM is told explicitly which CV facts are verified (years_experience,
  skills) vs. unverified, and must not state unverified facts as certain.
- Drafts are never sent anywhere automatically — they are returned to the UI
  for the user to copy, edit, and send themselves.