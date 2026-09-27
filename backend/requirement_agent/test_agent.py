"""
Self-contained tests for the Requirement/Intent-Match Agent.

Run with:
    python -m pytest backend/requirement_agent/test_agent.py -v
or directly:
    python backend/requirement_agent/test_agent.py
"""

import json
import sys
import os

# Ensure the backend package root is on the path when running directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from requirement_agent.agent import analyse, _heuristic_analyse, _clean_code


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_schema(result: dict, context: str = "") -> None:
    """Verify every required key is present and types are correct."""
    assert result.get("agent") == "requirement", f"{context}: agent field wrong"
    assert result["verdict"] in ("PASS", "CAUTION", "FAIL"), f"{context}: bad verdict"
    assert isinstance(result["score"], int), f"{context}: score must be int"
    assert 0 <= result["score"] <= 100, f"{context}: score out of range"
    assert isinstance(result["findings"], list), f"{context}: findings must be list"
    assert isinstance(result["missing_requirements"], list), f"{context}: missing must be list"
    assert isinstance(result["summary"], str), f"{context}: summary must be str"
    assert isinstance(result["met"], bool), f"{context}: met must be bool"
    assert isinstance(result["notes"], str), f"{context}: notes must be str"
    # met must be consistent with verdict
    assert result["met"] == (result["verdict"] == "PASS"), f"{context}: met/verdict mismatch"


# ---------------------------------------------------------------------------
# Test 1 — PASSING example
# (correct average with empty-list guard)
# ---------------------------------------------------------------------------

TASK_AVERAGE = (
    "Create a function that calculates the average of a list of numbers "
    "and safely handles an empty list by returning 0."
)

CODE_AVERAGE_CORRECT = """\
def average(numbers):
    if not numbers:
        return 0
    return sum(numbers) / len(numbers)
"""

def test_passing_average():
    result = analyse(CODE_AVERAGE_CORRECT, TASK_AVERAGE)
    _assert_schema(result, "passing_average")
    assert result["verdict"] == "PASS", (
        f"Expected PASS for correct implementation, got {result['verdict']}.\n"
        f"Findings: {result['findings']}\nMissing: {result['missing_requirements']}"
    )
    assert result["score"] >= 80, f"Score too low: {result['score']}"
    print(f"[PASS] test_passing_average — score={result['score']}, "
          f"verdict={result['verdict']}")
    print(f"       summary: {result['summary']}")


# ---------------------------------------------------------------------------
# Test 2 — MISMATCHED / PARTIAL example
# (average exists but empty-list guard is absent — matches the task's example)
# ---------------------------------------------------------------------------

CODE_AVERAGE_BAD = """\
def average(numbers):
    return sum(numbers) / len(numbers)
"""

def test_missing_empty_guard():
    result = analyse(CODE_AVERAGE_BAD, TASK_AVERAGE)
    _assert_schema(result, "missing_empty_guard")
    assert result["verdict"] in ("CAUTION", "FAIL"), (
        f"Expected CAUTION or FAIL for missing empty-list guard, "
        f"got {result['verdict']}."
    )
    # The 'empty' edge-case must be flagged
    missing_text = " ".join(result["missing_requirements"]).lower()
    findings_text = " ".join(result["findings"]).lower()
    assert "empty" in missing_text or "empty" in findings_text, (
        "Expected 'empty' guard to be flagged in missing_requirements or findings.\n"
        f"Missing: {result['missing_requirements']}\nFindings: {result['findings']}"
    )
    print(f"[PASS] test_missing_empty_guard — score={result['score']}, "
          f"verdict={result['verdict']}")
    print(f"       missing: {result['missing_requirements']}")
    print(f"       findings: {result['findings']}")


# ---------------------------------------------------------------------------
# Test 3 — No requirement (edge case for analyse())
# ---------------------------------------------------------------------------

def test_no_requirement():
    result = analyse("def foo(): pass", "")
    _assert_schema(result, "no_requirement")
    assert result["verdict"] == "PASS"
    assert result["met"] is True
    print(f"[PASS] test_no_requirement")


# ---------------------------------------------------------------------------
# Test 4 — Schema consistency
# ---------------------------------------------------------------------------

def test_output_is_json_serialisable():
    result = analyse(CODE_AVERAGE_BAD, TASK_AVERAGE)
    try:
        json.dumps(result)
    except TypeError as exc:
        raise AssertionError(f"Result is not JSON-serialisable: {exc}") from exc
    print("[PASS] test_output_is_json_serialisable")


# ---------------------------------------------------------------------------
# Test 5 — Contradiction detection
# ---------------------------------------------------------------------------

TASK_NO_PRINT = "Write a function that returns the doubled value. Do not use print."

CODE_WITH_PRINT = """\
def double(x):
    print(x * 2)
    return x * 2
"""

def test_contradiction_detection():
    result = analyse(CODE_WITH_PRINT, TASK_NO_PRINT)
    _assert_schema(result, "contradiction")
    findings_text = " ".join(result["findings"]).lower()
    assert "print" in findings_text or result["verdict"] in ("CAUTION", "FAIL"), (
        f"Expected contradiction about 'print' to be flagged.\n"
        f"Findings: {result['findings']}"
    )
    print(f"[PASS] test_contradiction_detection — verdict={result['verdict']}")
    print(f"       findings: {result['findings']}")


# ---------------------------------------------------------------------------
# Test 6 — Fully unrelated code
# ---------------------------------------------------------------------------

TASK_SORT = "Write a function that sorts a list in ascending order."

CODE_UNRELATED = """\
def greet(name):
    return "Hello, " + name
"""

def test_unrelated_code():
    result = analyse(CODE_UNRELATED, TASK_SORT)
    _assert_schema(result, "unrelated_code")
    assert result["verdict"] in ("CAUTION", "FAIL"), (
        f"Expected CAUTION or FAIL for completely unrelated code, "
        f"got {result['verdict']}."
    )
    print(f"[PASS] test_unrelated_code — verdict={result['verdict']}, "
          f"score={result['score']}")


# ---------------------------------------------------------------------------
# Test 7 — _clean_code strips diff noise
# ---------------------------------------------------------------------------

def test_clean_code_strips_diff_noise():
    diff = (
        "--- old.py\n"
        "+++ new.py\n"
        "@@ -1,3 +1,4 @@\n"
        " def foo():\n"
        "-    pass\n"
        "+    return 42\n"
    )
    cleaned = _clean_code(diff)
    assert "---" not in cleaned
    assert "+++" not in cleaned
    assert "@@" not in cleaned
    assert "pass" not in cleaned          # removed line must be stripped
    assert "return 42" in cleaned
    print("[PASS] test_clean_code_strips_diff_noise")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_passing_average,
        test_missing_empty_guard,
        test_no_requirement,
        test_output_is_json_serialisable,
        test_contradiction_detection,
        test_unrelated_code,
        test_clean_code_strips_diff_noise,
    ]
    failures = []
    print("=" * 60)
    for t in tests:
        try:
            t()
        except Exception as exc:
            failures.append((t.__name__, exc))
            print(f"[FAIL] {t.__name__}: {exc}")
    print("=" * 60)
    if failures:
        print(f"{len(failures)} test(s) FAILED.")
        sys.exit(1)
    else:
        print(f"All {len(tests)} tests passed.")
