"""
security_checkpoint.py — Security Checkpoint node (between Job Search and Matching).

Python-only responsibilities (no LLM):
  • PII redaction on all free-text posting fields (regex placeholders)
  • Prompt-injection heuristic scan on sanitized description
  • Fail-closed routing: any error or ambiguous match sets security_flag=True

Downstream LLM nodes (matching, skill_gap, cover_letter) must only receive
postings that have passed through this node.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from typing import Any

from google.adk.agents import Context
from google.adk.workflow import node

from job_finder_agent.core.pii_redaction import redact_pii
from job_finder_agent.core.prompt_injection import detect_prompt_injection

logger = logging.getLogger(__name__)

# Free-text fields on a JobSpy posting that may contain PII.
_FREE_TEXT_FIELDS = ("description", "company", "title", "location", "salary")


def _validate_output(output_data: Any, spec_schema_filename: str) -> None:
    """Calls the validate-node-output skill to validate output before returning."""
    skill_script = os.path.join(
        ".agents", "skills", "validate-node-output", "scripts", "validate.py"
    )
    schema_file = os.path.join(
        ".agents", "skills", "validate-node-output", "references", spec_schema_filename
    )

    if not os.path.exists(skill_script) or not os.path.exists(schema_file):
        logger.warning("Validation script or schema not found, skipping validation.")
        return

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(output_data, f)
        temp_path = f.name

    try:
        result = subprocess.run(
            ["python3", skill_script, temp_path, schema_file],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            logger.error(
                "Output validation failed:\n%s\n%s", result.stdout, result.stderr
            )
    finally:
        os.remove(temp_path)


def _redact_free_text_fields(posting: dict) -> tuple[dict, list[str]]:
    """Redact PII from every free-text field; return sanitized copy + categories."""
    sanitized = dict(posting)
    all_categories: set[str] = set()

    for field in _FREE_TEXT_FIELDS:
        raw = posting.get(field)
        if raw is None or not isinstance(raw, str) or not raw:
            continue
        clean, categories = redact_pii(raw)
        sanitized[field] = clean
        all_categories.update(categories)

    return sanitized, sorted(all_categories)


def _check_injection(description: str) -> tuple[bool, str | None]:
    """
    Run prompt-injection detection on sanitized description.
    Fail closed on exceptions or unexpected return shapes.
    """
    try:
        result = detect_prompt_injection(description)
        if not isinstance(result, tuple) or len(result) != 3:
            logger.error("detect_prompt_injection returned unexpected type: %r", result)
            return True, "fail_closed_due_to_error"

        is_flagged, reason, _confidence = result
        if not isinstance(is_flagged, bool):
            logger.error("detect_prompt_injection is_flagged not bool: %r", is_flagged)
            return True, "fail_closed_due_to_error"

        if is_flagged:
            if not isinstance(reason, str) or not reason.strip():
                return True, "fail_closed_due_to_error"
            return True, reason

        return False, None
    except Exception as exc:
        logger.error("Error in prompt injection detection: %s", exc)
        return True, "fail_closed_due_to_error"


def _process_posting(posting: dict) -> dict:
    """PII-redact then injection-scan a single raw posting."""
    sanitized, redacted_categories = _redact_free_text_fields(posting)
    security_flag, security_reason = _check_injection(
        sanitized.get("description", "") or ""
    )

    sanitized["redacted_categories"] = redacted_categories
    sanitized["security_flag"] = security_flag
    sanitized["security_reason"] = security_reason
    return sanitized


@node(rerun_on_resume=True)
async def security_checkpoint(
    ctx: Context,
    node_input: list | dict,
):
    """
    Security Checkpoint node: scrub PII and detect prompt injection on job postings.

    Input:  raw JobPosting dict or list thereof (from job_search_node)
    Output: sanitized postings with redacted_categories, security_flag, security_reason
    """
    try:
        if not node_input:
            return []

        postings = [node_input] if isinstance(node_input, dict) else list(node_input)
        sanitized_postings = [_process_posting(p) for p in postings]

        _validate_output(sanitized_postings, "security-schema.md")
        return sanitized_postings

    except Exception as exc:
        logger.error("security_checkpoint failed: %s", exc)
        return [
            {
                "job_id": "error",
                "title": "",
                "company": "",
                "location": "",
                "url": "",
                "description": "Error processing posting.",
                "redacted_categories": [],
                "security_flag": True,
                "security_reason": f"Node error: {exc}",
            }
        ]
