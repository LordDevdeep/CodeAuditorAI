"""
Tests for security_agent.agent

Run with:  python -m pytest backend/security_agent/test_agent.py -v
       or:  python backend/security_agent/test_agent.py
"""

import sys
import os

# Allow running from repo root without installing the package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from security_agent.agent import analyse  # noqa: E402

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _titles(result):
    return [f["title"] for f in result["findings"]]


def _lines_for(result, title):
    return [f["line_number"] for f in result["findings"] if f["title"] == title]


# ---------------------------------------------------------------------------
# Safe code — should produce no findings
# ---------------------------------------------------------------------------

SAFE_CODE = """\
def add(a, b):
    return a + b
"""


def test_safe_code_no_findings():
    r = analyse(SAFE_CODE)
    assert r["verdict"] == "PASS", f"Expected PASS, got {r['verdict']}"
    assert r["findings"] == [], f"Unexpected findings: {r['findings']}"
    assert r["score"] == 100
    assert r["issues"] == []
    print("PASS  test_safe_code_no_findings")


# ---------------------------------------------------------------------------
# Hardcoded password
# ---------------------------------------------------------------------------

HARDCODED_PASSWORD = """\
password = "admin123"

def login(user):
    pass
"""


def test_hardcoded_password():
    r = analyse(HARDCODED_PASSWORD)
    titles = _titles(r)
    assert "Hardcoded password" in titles, f"titles={titles}"
    assert r["verdict"] == "RISKY"
    # One HIGH finding → penalty 25 → score 75; still RISKY due to HIGH severity
    assert r["score"] < 90
    # Line number check — password is on line 1
    assert 1 in _lines_for(r, "Hardcoded password"), f"lines={_lines_for(r, 'Hardcoded password')}"
    print("PASS  test_hardcoded_password")


# ---------------------------------------------------------------------------
# SQL injection
# ---------------------------------------------------------------------------

SQL_INJECTION_CODE = """\
def get_user(username):
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    return db.execute(query)
"""


def test_sql_injection():
    r = analyse(SQL_INJECTION_CODE)
    titles = _titles(r)
    sql_titles = [t for t in titles if "SQL" in t]
    assert sql_titles, f"No SQL finding. titles={titles}"
    assert r["verdict"] == "RISKY"
    # The concatenation is on line 2
    sql_lines = [
        f["line_number"]
        for f in r["findings"]
        if "SQL" in f["title"]
    ]
    assert 2 in sql_lines, f"SQL finding not on line 2: {sql_lines}"
    print("PASS  test_sql_injection")


# ---------------------------------------------------------------------------
# Combined risky example (password + SQL)
# ---------------------------------------------------------------------------

RISKY_CODE = """\
password = "admin123"

def get_user(username):
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    return db.execute(query)
"""


def test_risky_combined():
    r = analyse(RISKY_CODE)
    titles = _titles(r)
    assert "Hardcoded password" in titles, f"titles={titles}"
    assert any("SQL" in t for t in titles), f"titles={titles}"
    assert r["verdict"] == "RISKY"
    # Two HIGH findings → penalty 50 → score 50 (or lower with more matches)
    assert r["score"] < 70
    # legacy issues list populated
    assert len(r["issues"]) >= 2
    print("PASS  test_risky_combined")


# ---------------------------------------------------------------------------
# eval()
# ---------------------------------------------------------------------------

EVAL_CODE = """\
def run_user_input(user_input):
    result = eval(user_input)
    return result
"""


def test_eval_detected():
    r = analyse(EVAL_CODE)
    titles = _titles(r)
    assert "Use of eval()" in titles, f"titles={titles}"
    assert r["verdict"] == "RISKY"
    assert 2 in _lines_for(r, "Use of eval()"), f"lines={_lines_for(r, 'Use of eval()')}"
    print("PASS  test_eval_detected")


# ---------------------------------------------------------------------------
# exec()
# ---------------------------------------------------------------------------

EXEC_CODE = """\
def run_code(code_string):
    exec(code_string)
"""


def test_exec_detected():
    r = analyse(EXEC_CODE)
    titles = _titles(r)
    assert "Use of exec()" in titles, f"titles={titles}"
    assert r["verdict"] == "RISKY"
    print("PASS  test_exec_detected")


# ---------------------------------------------------------------------------
# Bare except
# ---------------------------------------------------------------------------

BARE_EXCEPT_CODE = """\
def risky():
    try:
        do_something()
    except:
        pass
"""


def test_bare_except_detected():
    r = analyse(BARE_EXCEPT_CODE)
    titles = _titles(r)
    assert "Bare except clause" in titles, f"titles={titles}"
    # One MEDIUM finding: penalty=10, score=90; verdict boundary → PASS or CAUTION acceptable
    assert r["score"] <= 90
    # bare except is on line 4
    assert 4 in _lines_for(r, "Bare except clause"), f"lines={_lines_for(r, 'Bare except clause')}"
    print("PASS  test_bare_except_detected")


# ---------------------------------------------------------------------------
# Broad except Exception
# ---------------------------------------------------------------------------

BROAD_EXCEPT_CODE = """\
def risky():
    try:
        do_something()
    except Exception:
        pass
"""


def test_broad_except_detected():
    r = analyse(BROAD_EXCEPT_CODE)
    titles = _titles(r)
    assert "Overly broad exception handling (Exception)" in titles, f"titles={titles}"
    print("PASS  test_broad_except_detected")


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------

API_KEY_CODE = """\
api_key = "sk-abc123secretkey"
client = OpenAI(api_key=api_key)
"""


def test_api_key_detected():
    r = analyse(API_KEY_CODE)
    titles = _titles(r)
    assert "Hardcoded API key / secret token" in titles, f"titles={titles}"
    assert r["verdict"] == "RISKY"
    assert 1 in _lines_for(r, "Hardcoded API key / secret token")
    print("PASS  test_api_key_detected")


# ---------------------------------------------------------------------------
# Diff format (lines prefixed with +)
# ---------------------------------------------------------------------------

DIFF_FORMAT = """\
+password = "secret"
+def add(a, b):
+    return a + b
"""


def test_diff_format_strips_marker():
    r = analyse(DIFF_FORMAT)
    titles = _titles(r)
    assert "Hardcoded password" in titles, f"titles={titles}"
    # password line is line 1 in the diff
    assert 1 in _lines_for(r, "Hardcoded password")
    # safe lines 2-3 should not produce findings
    assert not any(f["line_number"] in (2, 3) and "password" in f["title"].lower()
                   for f in r["findings"])
    print("PASS  test_diff_format_strips_marker")


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

def test_return_structure():
    r = analyse(SAFE_CODE)
    assert r["agent"] == "security"
    assert r["verdict"] in ("PASS", "CAUTION", "RISKY")
    assert isinstance(r["score"], int)
    assert 0 <= r["score"] <= 100
    assert isinstance(r["findings"], list)
    assert isinstance(r["summary"], str)
    assert isinstance(r["issues"], list)  # legacy key present
    print("PASS  test_return_structure")


def test_finding_fields():
    r = analyse(HARDCODED_PASSWORD)
    for f in r["findings"]:
        for key in ("severity", "category", "title", "description", "line_number", "recommendation"):
            assert key in f, f"Missing key '{key}' in finding: {f}"
        assert f["severity"] in ("HIGH", "MEDIUM", "LOW")
    print("PASS  test_finding_fields")


# ---------------------------------------------------------------------------
# Runner when executed directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_safe_code_no_findings,
        test_hardcoded_password,
        test_sql_injection,
        test_risky_combined,
        test_eval_detected,
        test_exec_detected,
        test_bare_except_detected,
        test_broad_except_detected,
        test_api_key_detected,
        test_diff_format_strips_marker,
        test_return_structure,
        test_finding_fields,
    ]

    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            print(f"FAIL  {t.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"ERROR {t.__name__}: {exc}")
            failed += 1

    print(f"\n{'All tests passed.' if failed == 0 else f'{failed} test(s) failed.'}")
    sys.exit(0 if failed == 0 else 1)
