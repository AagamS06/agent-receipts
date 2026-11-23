import json
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from agent_receipts.cli import app
from agent_receipts.schema import receipt_schema, schema_text

runner = CliRunner()
ROOT = Path(__file__).parent.parent
COMMITTED = ROOT / "schema" / "receipt.v1.json"
FIX = Path(__file__).parent / "fixtures"


def test_committed_schema_is_current() -> None:
    # If this fails after a model change: agent-receipts schema -o schema/receipt.v1.json
    assert COMMITTED.read_text(encoding="utf-8") == schema_text()


def test_schema_is_valid_draft_2020_12() -> None:
    jsonschema.Draft202012Validator.check_schema(receipt_schema())


@pytest.mark.parametrize("fixture", sorted(p.name for p in FIX.glob("*.jsonl")))
def test_every_fixture_receipt_validates(fixture: str, tmp_path: Path) -> None:
    out = tmp_path / "r.json"
    res = runner.invoke(app, ["render", str(FIX / fixture), "-f", "json", "-o", str(out)])
    assert res.exit_code in (0, 1), res.stdout
    jsonschema.validate(json.loads(out.read_text()), receipt_schema())


def test_schema_rejects_bad_status() -> None:
    bad = {"verdict": {"status": "MAYBE", "reason": "x"}}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, receipt_schema())


def test_schema_command_and_check(tmp_path: Path) -> None:
    res = runner.invoke(app, ["schema"])
    assert res.exit_code == 0 and json.loads(res.stdout)["$id"].endswith("receipt.v1.json")
    target = tmp_path / "s.json"
    assert runner.invoke(app, ["schema", "-o", str(target)]).exit_code == 0
    assert runner.invoke(app, ["schema", "--check", str(target)]).exit_code == 0
    target.write_text("{}\n")
    assert runner.invoke(app, ["schema", "--check", str(target)]).exit_code == 1
    assert runner.invoke(app, ["schema", "--check", str(tmp_path / "missing.json")]).exit_code == 2
