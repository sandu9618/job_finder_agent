import logging
import json
import os
import subprocess
import tempfile
from typing import Any

from google.adk.agents import Context
from google.adk.workflow import node

logger = logging.getLogger(__name__)

def _validate_output(output_data: Any, spec_schema_filename: str):
    """
    Calls the validate-node-output skill to validate output before returning.
    """
    skill_script = os.path.join(".agents", "skills", "validate-node-output", "scripts", "validate.py")
    schema_file = os.path.join(".agents", "skills", "validate-node-output", "references", spec_schema_filename)
    
    if not os.path.exists(skill_script) or not os.path.exists(schema_file):
        logger.warning("Validation script or schema not found, skipping validation.")
        return

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(output_data, f)
        temp_path = f.name
        
    try:
        result = subprocess.run(
            ["python", skill_script, temp_path, schema_file],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            logger.error(f"Output validation failed:\n{result.stdout}\n{result.stderr}")
            # If fail-closed is required on validation error, you can raise or return error here.
    finally:
        os.remove(temp_path)

@node(rerun_on_resume=True)
async def TODO_NODE_NAME(
    ctx: Context,
    node_input: list | dict,
):
    """
    TODO: Add node description.
    """
    try:
        # TODO: Implement node business logic
        output = {}
        
        # Validate node output
        # TODO: update schema filename to match your node's spec
        _validate_output(output, "TODO_SCHEMA_FILE.md")
        
        return output

    except Exception as exc:
        logger.error("TODO_NODE_NAME failed: %s", exc)
        # Fail closed edge case: return structured errors instead of raising uncaught
        return {"error": str(exc), "security_flag": True}
