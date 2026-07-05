"""Patch installed python-jobspy to recognize Sri Lanka as a valid country."""
from __future__ import annotations

from pathlib import Path

import jobspy.model

MODEL_PATH = Path(jobspy.model.__file__)
MARKER = "SRI_LANKA"
INSERT_AFTER = '    SINGAPORE = ("singapore", "sg", "sg")'


def main() -> None:
    text = MODEL_PATH.read_text()
    if MARKER in text:
        return
    if INSERT_AFTER not in text:
        raise RuntimeError("Could not find insertion point in jobspy.model")
    text = text.replace(
        INSERT_AFTER,
        INSERT_AFTER + '\n    SRI_LANKA = ("sri lanka", "lk")',
    )
    MODEL_PATH.write_text(text)
    print("Patched jobspy.model: added SRI_LANKA")


if __name__ == "__main__":
    main()
