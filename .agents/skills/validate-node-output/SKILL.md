---
name: validate-node-output
description: Validate a graph node's output JSON against the schema defined for that node in specs/. Use this whenever writing or editing code for a node under job_finder_agent/nodes/, before considering the node's output handling complete.
---

When writing or editing any node file, identify which spec it implements. Run `scripts/validate.py` against a representative sample output and the matching reference schema, and if validation fails, fix the node's output construction before continuing. Don't just report the failure and move on.

### Example

Validating a sample CV parser output:

Given `sample_cv.json`:
```json
{
  "raw_text": "Experienced engineer...",
  "skills": ["Python", "AWS"],
  "titles": ["Senior Engineer", "Developer"],
  "years_experience": 5.5,
  "education": ["BSc Computer Science"],
  "location": "Remote",
  "summary": "A seasoned engineer with..."
}
```

Run the validation:
```bash
python .agents/skills/validate-node-output/scripts/validate.py sample_cv.json .agents/skills/validate-node-output/references/cv-parsing-schema.md
```

**Pass Case:**
```
PASS
```

**Fail Case (missing 'titles'):**
```
Validation Failed:
- Item 0: Missing required field 'titles'
```
