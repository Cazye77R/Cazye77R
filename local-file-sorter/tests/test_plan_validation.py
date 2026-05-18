"""Test strict LLM plan validation (validate_plan + schema guards)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.llm.ollama_client import PlanValidationError, validate_plan
from src.llm.schemas import OpType, SortAction, SortPlan


def _action(op_type, source, destination, reason="test"):
    return SortAction(op_type=op_type, source=source,
                      destination=destination, reason=reason)


# ---------------------------------------------------------------------------
# Schema-level guards (caught before validate_plan)
# ---------------------------------------------------------------------------

def test_unknown_op_type_rejected_by_schema():
    with pytest.raises((ValueError, ValidationError)):
        SortPlan.model_validate({
            "actions": [{"op_type": "delete", "destination": "/x", "reason": "r"}],
            "summary": "bad",
        })


def test_copy_op_type_rejected_by_schema():
    with pytest.raises((ValueError, ValidationError)):
        SortPlan.model_validate({
            "actions": [{"op_type": "copy", "source": "/a", "destination": "/b", "reason": "r"}],
            "summary": "bad",
        })


# ---------------------------------------------------------------------------
# validate_plan – path safety
# ---------------------------------------------------------------------------

def test_valid_plan_passes(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    src = root / "a.txt"
    src.touch()

    plan = SortPlan(
        actions=[
            _action(OpType.create_folder, None, root / "sub"),
            _action(OpType.move, src, root / "sub" / "a.txt"),
        ],
        summary="ok",
    )
    validate_plan(plan, root)   # must not raise


def test_destination_outside_root_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    src = root / "a.txt"
    src.touch()

    plan = SortPlan(
        actions=[_action(OpType.move, src, tmp_path / "outside" / "a.txt")],
        summary="bad",
    )
    with pytest.raises(PlanValidationError, match="außerhalb"):
        validate_plan(plan, root)


def test_source_outside_root_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "other" / "b.txt"
    outside.parent.mkdir()
    outside.touch()

    plan = SortPlan(
        actions=[_action(OpType.move, outside, root / "b.txt")],
        summary="bad",
    )
    with pytest.raises(PlanValidationError, match="außerhalb"):
        validate_plan(plan, root)


def test_nonexistent_source_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()

    plan = SortPlan(
        actions=[_action(OpType.move, root / "ghost.txt", root / "sub" / "ghost.txt")],
        summary="bad",
    )
    with pytest.raises(PlanValidationError, match="existiert nicht"):
        validate_plan(plan, root)


def test_dotdot_destination_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    sneaky = root / ".." / "evil" / "file.txt"

    plan = SortPlan(
        actions=[_action(OpType.create_folder, None, sneaky)],
        summary="bad",
    )
    with pytest.raises(PlanValidationError, match="außerhalb"):
        validate_plan(plan, root)


def test_one_bad_action_rejects_whole_plan(tmp_path):
    """Even if most actions are valid, one invalid one rejects everything."""
    root = tmp_path / "root"
    root.mkdir()
    good_src = root / "good.txt"
    good_src.touch()

    plan = SortPlan(
        actions=[
            _action(OpType.move, good_src, root / "good_moved.txt"),
            _action(OpType.move, root / "missing.txt", root / "x.txt"),  # bad
        ],
        summary="mixed",
    )
    with pytest.raises(PlanValidationError):
        validate_plan(plan, root)


def test_empty_plan_accepted(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    plan = SortPlan(actions=[], summary="nothing to do")
    validate_plan(plan, root)   # must not raise


def test_create_folder_inside_root_accepted(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    plan = SortPlan(
        actions=[_action(OpType.create_folder, None, root / "a" / "b")],
        summary="ok",
    )
    validate_plan(plan, root)
