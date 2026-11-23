"""JSON Schema for the receipt contract (schema version 1).

The schema is generated from the pydantic models so it can never drift from what
``render -f json`` writes. A copy is committed at ``schema/receipt.v1.json`` and a test
fails if the two differ.
"""

from __future__ import annotations

import json
from typing import Any

from agent_receipts.models import Receipt

SCHEMA_ID = "https://raw.githubusercontent.com/AagamS06/agent-receipts/main/schema/receipt.v1.json"


def receipt_schema() -> dict[str, Any]:
    schema = Receipt.model_json_schema(mode="serialization")
    out: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "agent-receipts receipt (schema version 1)",
        "description": (
            "A receipt for one or more coding-agent sessions: verification verdict, "
            "risk findings, files changed, usage and assumptions. Written by "
            "`agent-receipts render -f json`."
        ),
    }
    out.update({k: v for k, v in schema.items() if k not in {"title", "description"}})
    return out


def schema_text() -> str:
    return json.dumps(receipt_schema(), indent=2, ensure_ascii=False) + "\n"
