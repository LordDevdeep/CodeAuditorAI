"""
Security Agent — static analysis for common security risks in AI-generated code.

Detects:
1. Hardcoded passwords, API keys, tokens, or other secrets.
2. Dangerous use of eval() or exec().
3. SQL injection risk from unsafe string-built SQL queries.
4. Missing or obviously inadequate input validation.
5. Bare or overly broad exception handling.
6. Dangerous shell / subprocess calls with user-controlled data.

Returns a structured JSON-compatible dict with verdict, score, and per-finding
details. Also includes a legacy ``issues`` list so the coordinator continues to
work without modification.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------------
# Rule definitions
# Each rule is a dict with:
#   pattern  – compiled regex applied to individual lines
#   severity – HIGH / MEDIUM / LOW
#   category – short category label
#   title    – concise title
#   description – one-sentence explanation
#   recommendation – how to fix it
# ---------------------------------------------------------------------------

_RULES = [
    # ── Secrets ────────────────────────────────────────────────────────────
    {
        "pattern": re.compile(
            r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{1,}["\']'
        ),
        "severity": "HIGH",
        "category": "Secrets",
        "title": "Hardcoded password",
        "description": (
            "A password is assigned as a literal string in source code. "
            "Anyone with read access to the repository can extract it."
        ),
        "recommendation": (
            "Read credentials from environment variables or a secrets manager "
            "(e.g. os.environ['DB_PASSWORD']) and never commit secrets to source control."
        ),
    },
    {
        "pattern": re.compile(
            r'(?i)(api_key|apikey|api_secret|secret_key|access_token|auth_token|'
            r'private_key|client_secret)\s*=\s*["\'][^"\']{1,}["\']'
        ),
        "severity": "HIGH",
        "category": "Secrets",
        "title": "Hardcoded API key / secret token",
        "description": (
            "An API key, secret, or token is embedded as a literal in source code, "
            "making it trivially extractable from version control history."
        ),
        "recommendation": (
            "Store secrets in environment variables or a vault and load them at runtime."
        ),
    },
    # ── Code injection ──────────────────────────────────────────────────────
    {
        "pattern": re.compile(r'\beval\s*\('),
        "severity": "HIGH",
        "category": "Code Injection",
        "title": "Use of eval()",
        "description": (
            "eval() executes arbitrary code from a string. "
            "If the string contains user-controlled data, this is a critical code-injection vulnerability."
        ),
        "recommendation": (
            "Replace eval() with a safe alternative such as ast.literal_eval() for data parsing, "
            "or redesign the logic to avoid dynamic code execution entirely."
        ),
    },
    {
        "pattern": re.compile(r'\bexec\s*\('),
        "severity": "HIGH",
        "category": "Code Injection",
        "title": "Use of exec()",
        "description": (
            "exec() executes arbitrary code from a string and carries the same "
            "code-injection risks as eval()."
        ),
        "recommendation": (
            "Avoid exec() where possible. If dynamic dispatch is required, use "
            "a well-defined dispatch table (dict mapping names to functions)."
        ),
    },
    # ── SQL injection ───────────────────────────────────────────────────────
    {
        "pattern": re.compile(
            r'(?i)(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE)\b.*["\'].+["\']\s*\+',
            re.DOTALL,
        ),
        "severity": "HIGH",
        "category": "SQL Injection",
        "title": "SQL query built by string concatenation",
        "description": (
            "A SQL statement is assembled by concatenating strings, which may include "
            "user-supplied values. This is the classic SQL-injection pattern."
        ),
        "recommendation": (
            "Use parameterised queries or an ORM. "
            "Example: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))"
        ),
    },
    {
        "pattern": re.compile(
            r'(?i)(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE)\b.*\+\s*\w'
        ),
        "severity": "HIGH",
        "category": "SQL Injection",
        "title": "SQL query built by string concatenation (variable)",
        "description": (
            "A SQL statement appears to concatenate a variable directly into the query string, "
            "creating a potential SQL-injection vector."
        ),
        "recommendation": (
            "Use parameterised queries or prepared statements. "
            "Never interpolate raw user input into SQL."
        ),
    },
    # ── Shell injection ─────────────────────────────────────────────────────
    {
        "pattern": re.compile(
            r'(?i)(os\.system|subprocess\.call|subprocess\.run|subprocess\.Popen|'
            r'commands\.getoutput|os\.popen)\s*\('
        ),
        "severity": "MEDIUM",
        "category": "Shell Injection",
        "title": "Dangerous shell / subprocess call",
        "description": (
            "A shell execution function is invoked. If the command string includes "
            "user-controlled data without sanitisation, this enables shell injection."
        ),
        "recommendation": (
            "Pass arguments as a list rather than a shell string and set shell=False. "
            "Validate and whitelist any user input before use in shell commands."
        ),
    },
    # ── Exception handling ──────────────────────────────────────────────────
    {
        "pattern": re.compile(r'^\s*except\s*:\s*$'),
        "severity": "MEDIUM",
        "category": "Error Handling",
        "title": "Bare except clause",
        "description": (
            "A bare 'except:' catches every possible exception including "
            "KeyboardInterrupt and SystemExit, silently masking real errors."
        ),
        "recommendation": (
            "Catch specific exceptions (e.g. except ValueError:) and log or "
            "re-raise unexpected ones so failures are not silently hidden."
        ),
    },
    {
        "pattern": re.compile(r'^\s*except\s+Exception\s*:\s*$'),
        "severity": "LOW",
        "category": "Error Handling",
        "title": "Overly broad exception handling (Exception)",
        "description": (
            "Catching the base Exception class is almost as broad as a bare except "
            "and can hide programming errors and unexpected conditions."
        ),
        "recommendation": (
            "Catch the most specific exception types relevant to the operation. "
            "At minimum, log the exception before swallowing it."
        ),
    },
    {
        "pattern": re.compile(r'^\s*except\s+Exception\s+as\s+\w+\s*:\s*$'),
        "severity": "LOW",
        "category": "Error Handling",
        "title": "Overly broad exception handling (Exception as ...)",
        "description": (
            "Catching the base Exception class with a variable is still too broad "
            "and may hide unexpected errors if the body does not re-raise or log them."
        ),
        "recommendation": (
            "Prefer catching specific exception types. Ensure the handler "
            "at least logs the exception."
        ),
    },
    # ── Input validation ────────────────────────────────────────────────────
    {
        "pattern": re.compile(r'request\.(args|form|json|data|get_json)\b'),
        "severity": "LOW",
        "category": "Input Validation",
        "title": "User input accessed without visible validation",
        "description": (
            "Request data is read from the HTTP request object. "
            "Without explicit type-checking or sanitisation, this may process "
            "malformed or malicious input."
        ),
        "recommendation": (
            "Validate and sanitise all user-supplied values before use: "
            "check types, enforce length limits, and use a validation library "
            "such as marshmallow, pydantic, or WTForms."
        ),
    },
]


def _deduplicate(findings: list[dict]) -> list[dict]:
    """Remove findings with identical (title, line_number) pairs."""
    seen: set[tuple] = set()
    result = []
    for f in findings:
        key = (f["title"], f["line_number"])
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


def _calculate_score(findings: list[dict]) -> int:
    if not findings:
        return 100

    high = sum(1 for f in findings if f["severity"] == "HIGH")
    medium = sum(1 for f in findings if f["severity"] == "MEDIUM")
    low = sum(1 for f in findings if f["severity"] == "LOW")

    # Penalty: HIGH=25, MEDIUM=10, LOW=4 — capped at 100 deduction
    penalty = min(high * 25 + medium * 10 + low * 4, 100)
    return max(0, 100 - penalty)


def _verdict(score: int, findings: list[dict]) -> str:
    high_count = sum(1 for f in findings if f["severity"] == "HIGH")
    if high_count > 0 or score < 40:
        return "RISKY"
    if score < 90:
        return "CAUTION"
    return "PASS"


def analyse(diff: str, language: Optional[str] = None) -> dict:
    """
    Scan *diff* (or any source code string) for common security issues.

    Parameters
    ----------
    diff:
        The source code or diff to audit.
    language:
        Optional programming language hint (not currently used for rule
        selection but included for forward-compatibility).

    Returns
    -------
    dict
        Structured audit result. Includes a legacy ``issues`` list for
        backward compatibility with the existing coordinator.
    """
    lines = diff.splitlines()
    findings: list[dict] = []

    for rule in _RULES:
        for lineno, line in enumerate(lines, start=1):
            # Strip leading diff markers (+ / -) before matching
            stripped = line.lstrip("+-")
            if rule["pattern"].search(stripped):
                findings.append(
                    {
                        "severity": rule["severity"],
                        "category": rule["category"],
                        "title": rule["title"],
                        "description": rule["description"],
                        "line_number": lineno,
                        "recommendation": rule["recommendation"],
                    }
                )

    findings = _deduplicate(findings)
    score = _calculate_score(findings)
    verdict = _verdict(score, findings)

    high = sum(1 for f in findings if f["severity"] == "HIGH")
    medium = sum(1 for f in findings if f["severity"] == "MEDIUM")
    low = sum(1 for f in findings if f["severity"] == "LOW")

    if not findings:
        summary = "No security issues detected."
    else:
        parts = []
        if high:
            parts.append(f"{high} HIGH")
        if medium:
            parts.append(f"{medium} MEDIUM")
        if low:
            parts.append(f"{low} LOW")
        summary = f"{len(findings)} finding(s): {', '.join(parts)}."

    return {
        # New structured format
        "agent": "security",
        "verdict": verdict,
        "score": score,
        "findings": findings,
        "summary": summary,
        # Legacy key — keeps the coordinator working without changes
        "issues": [f["title"] for f in findings],
    }
