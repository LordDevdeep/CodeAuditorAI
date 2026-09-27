"""
Tests for impact_agent.agent — four scenarios:
1. Target function with callers in other source files.
2. Target with related test files.
3. Target with no obvious dependencies (SAFE).
4. Legacy diff-based mode (backward compat with coordinator).
"""

import sys
import os

# Ensure the backend package root is on sys.path when run directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from impact_agent.agent import analyse


# ---------------------------------------------------------------------------
# Sample mini-codebase shared across tests
# ---------------------------------------------------------------------------

SAMPLE_FILES = {
    # The module being targeted
    "utils/math_utils.py": """\
def calculate_discount(price, pct):
    \"\"\"Return discounted price.\"\"\"
    return price * (1 - pct / 100)
""",
    # Source file that imports and calls the function
    "services/order_service.py": """\
from utils.math_utils import calculate_discount

def apply_promo(order):
    return calculate_discount(order['price'], 10)
""",
    # Another source file that also calls it
    "api/cart_api.py": """\
from utils import math_utils

def cart_total(items):
    return sum(math_utils.calculate_discount(i['price'], i['disc']) for i in items)
""",
    # Test file
    "tests/test_math_utils.py": """\
import pytest
from utils.math_utils import calculate_discount

def test_zero_discount():
    assert calculate_discount(100, 0) == 100

def test_full_discount():
    assert calculate_discount(100, 100) == 0
""",
    # Documentation that mentions it
    "docs/pricing.md": """\
# Pricing Logic

The `calculate_discount` function lives in `utils/math_utils.py`.
Use it to apply percentage-based discounts.
""",
    # Unrelated file — should NOT appear in results
    "services/auth_service.py": """\
def login(username, password):
    return username == 'admin' and password == 'secret'
""",
}


# ---------------------------------------------------------------------------
# Test 1: target function that has callers
# ---------------------------------------------------------------------------

def test_target_function_with_callers():
    result = analyse(target="calculate_discount", files=SAMPLE_FILES)

    assert result["agent"] == "impact"
    assert result["verdict"] in ("CAUTION", "RISKY")
    assert result["score"] > 0

    affected = result["affected_files"]
    # Both source files and the test must be detected
    assert "services/order_service.py" in affected
    assert "api/cart_api.py" in affected
    assert "tests/test_math_utils.py" in affected

    # Unrelated file must NOT appear
    assert "services/auth_service.py" not in affected

    print("\n[test_target_function_with_callers] PASSED")
    print("  verdict:", result["verdict"], "| score:", result["score"])
    print("  affected_files:", result["affected_files"])
    print("  findings:", result["findings"])


# ---------------------------------------------------------------------------
# Test 2: target file with related tests
# ---------------------------------------------------------------------------

def test_target_file_with_tests():
    result = analyse(target="utils/math_utils.py", files=SAMPLE_FILES)

    assert result["agent"] == "impact"
    assert result["verdict"] in ("CAUTION", "RISKY")

    affected = result["affected_files"]
    assert "tests/test_math_utils.py" in affected

    # Ensure test classification appears in components
    test_comps = [c for c in result["affected_components"] if c.startswith("test:")]
    assert len(test_comps) >= 1

    print("\n[test_target_file_with_tests] PASSED")
    print("  verdict:", result["verdict"], "| score:", result["score"])
    print("  affected_files:", result["affected_files"])


# ---------------------------------------------------------------------------
# Test 3: target with no obvious dependencies → SAFE
# ---------------------------------------------------------------------------

def test_target_no_dependencies():
    isolated_files = {
        "module_a.py": "def foo(): pass",
        "module_b.py": "def bar(): pass",
    }
    result = analyse(target="completely_unknown_function", files=isolated_files)

    assert result["agent"] == "impact"
    assert result["verdict"] == "SAFE"
    assert result["score"] == 0
    assert result["affected_files"] == []

    print("\n[test_target_no_dependencies] PASSED")
    print("  verdict:", result["verdict"], "| score:", result["score"])


# ---------------------------------------------------------------------------
# Test 4: legacy diff mode (coordinator backward compat)
# ---------------------------------------------------------------------------

def test_legacy_diff_mode():
    sample_diff = """\
--- a/utils/math_utils.py
+++ b/utils/math_utils.py
@@ -1,3 +1,4 @@
 def calculate_discount(price, pct):
-    return price * (1 - pct / 100)
+    if pct < 0 or pct > 100:
+        raise ValueError("pct must be 0-100")
+    return price * (1 - pct / 100)
"""
    result = analyse(diff=sample_diff)

    # Legacy result keys
    assert "risk" in result
    assert "files_changed" in result
    assert result["risk"] in ("low", "medium", "high")

    # Must NOT have the new-style keys
    assert "agent" not in result

    print("\n[test_legacy_diff_mode] PASSED")
    print("  risk:", result["risk"])
    print("  files_changed:", result["files_changed"])


# ---------------------------------------------------------------------------
# Test 5: documentation references detected
# ---------------------------------------------------------------------------

def test_doc_reference_detected():
    result = analyse(target="calculate_discount", files=SAMPLE_FILES)

    doc_comps = [c for c in result["affected_components"] if c.startswith("doc:")]
    assert len(doc_comps) >= 1, "Expected at least one doc reference"

    print("\n[test_doc_reference_detected] PASSED")
    print("  doc components:", doc_comps)


# ---------------------------------------------------------------------------
# Test 6: empty files dict → SAFE
# ---------------------------------------------------------------------------

def test_empty_codebase():
    result = analyse(target="some_function", files={})

    assert result["verdict"] == "SAFE"
    assert result["score"] == 0
    assert result["affected_files"] == []

    print("\n[test_empty_codebase] PASSED")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    test_target_function_with_callers()
    test_target_file_with_tests()
    test_target_no_dependencies()
    test_legacy_diff_mode()
    test_doc_reference_detected()
    test_empty_codebase()
    print("\nAll tests passed.")
