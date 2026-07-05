---
name: scaffold-graph-node
description: Scaffold a new ADK 2.0 graph node under job_finder_agent/nodes/ with the standard structure - input handling, try/except wrapping for fail-closed edge cases, and a closing validation-node-output check. Use this whenever creating a new node for the job-finder graph.
---

When asked to build a new node:
1. Run `scripts/scaffold_node.py` with the node's name to generate the skeleton file.
2. Read `examples/matching_node.py` as the style reference for filling in the TODOs.
3. Identify which `specs/*.md` file defines this node's behavior and implement the Gherkin edge cases as explicit branches, not just the happy path.
4. Before considering the node done, invoke the `validate-node-output` skill against a sample output.

### Example

Scaffolding a node called "skill_gap", filling it in against `specs/job-matching-scoring.md`'s skill-gap behavior, and validating the result:

1. Scaffold the node:
```bash
python .agents/skills/scaffold-graph-node/scripts/scaffold_node.py skill_gap
```
*(This creates `job_finder_agent/nodes/skill_gap.py`)*

2. Open the created file and implement the logic based on the spec edge cases (e.g. failing closed on errors, returning structured objects). Use `examples/matching_node.py` for reference.

3. At the end of the node's logic, ensure it calls `_validate_output` with the correct schema file from `validate-node-output/references/` (e.g. `"job-matching-scoring.md"`).

4. Finally, validate the node output with `validate-node-output`.
