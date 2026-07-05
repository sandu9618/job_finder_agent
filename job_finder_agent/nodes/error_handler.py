"""
error_handler.py — terminal node for the CV parse error branch.

Emits a user-facing content event explaining the error and returns None
so the graph terminates cleanly (no downstream trigger).
"""

from __future__ import annotations

import logging

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.genai import types

from ..schemas import CVParseError

logger = logging.getLogger(__name__)


def error_handler_node(ctx: Context, node_input: dict) -> None:
    """
    Receives a CVParseError dict, emits a human-readable message to the UI,
    and returns None (no output event → graph terminates).
    """
    try:
        err = CVParseError(**node_input)
    except Exception:
        err = CVParseError(reason="unknown", message=str(node_input))

    logger.error("CV parse error [%s]: %s", err.reason, err.message)

    reason_messages = {
        "no_text_layer": (
            "⚠️ Your PDF appears to be image-only (scanned document with no text layer). "
            "Please re-upload a text-based PDF, or use OCR software to convert it first."
        ),
        "corrupted": (
            "⚠️ Your PDF could not be opened — it may be password-protected or corrupted. "
            "Please unlock or repair the file and try again."
        ),
        "no_pdf": (
            "⚠️ No PDF was found in your upload. Please attach a PDF file."
        ),
    }
    user_message = reason_messages.get(
        err.reason,
        f"⚠️ CV parsing failed ({err.reason}): {err.message}. Please try again with a different file.",
    )

    # Emit content to the web UI (Event.output is internal only).
    ctx.output = None  # explicitly no output — terminates graph
    return Event(
        content=types.Content(
            role="model",
            parts=[types.Part.from_text(text=user_message)],
        )
    )
