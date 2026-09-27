"""
Security Agent — scans the diff for common security red flags.

MVP stub: regex-based pattern matching.
Replace / extend with an LLM call or a dedicated SAST tool for the real thing.
"""

import re
import ast

# Each entry: (label, compiled regex)
# All patterns use re.IGNORECASE for case-insensitive matching.
PATTERNS = [
    (
        "Hardcoded password",
        # Matches both assignment (password = "x") and comparison (password == "x" / "x" == password)
        re.compile(
            r'(password|passwd|pwd)\s*==?\s*["\'].+["\']'
            r'|["\'].+["\']\s*==\s*(password|passwd|pwd)',
            re.IGNORECASE,
        ),
    ),
    (
        "Hardcoded API key / secret",
        # Matches both assignment and comparison for key/secret/token names
        re.compile(
            r'(api_key|secret|token)\s*==?\s*["\'].+["\']'
            r'|["\'].+["\']\s*==\s*(api_key|secret|token)',
            re.IGNORECASE,
        ),
    ),
    (
        "SQL string concatenation (possible injection)",
        re.compile(r'(SELECT|INSERT|UPDATE|DELETE).+\+', re.IGNORECASE),
    ),
    ("Use of eval()", re.compile(r'\beval\s*\(')),
    ("Use of exec()", re.compile(r'\bexec\s*\(')),
    (
        "Dangerous shell call",
        re.compile(r'(os\.system|subprocess\.call|subprocess\.run)\s*\(', re.IGNORECASE),
    ),
    (
        "Bare except block (swallows all errors)",
        re.compile(r'^\s*except\s*:', re.MULTILINE),
    ),
]


def _check_missing_input_validation(diff: str) -> list[str]:
    """
    Parse each function definition found in the diff and flag any that have
    parameters but contain no guard clauses (if/raise/assert/isinstance checks).
    Uses AST parsing so it is accurate rather than purely lexical.
    Falls back silently if the snippet is not valid Python.
    """
    issues = []
    try:
        tree = ast.parse(diff)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        # Ignore functions with no parameters (or only self/cls)
        params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
        if not params:
            continue

        # Look for any validation-like statement in the function body
        has_validation = False
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.Assert, ast.Raise)):
                has_validation = True
                break
            # isinstance(...) call also counts
            if (
                isinstance(child, ast.Call)
                and isinstance(getattr(child, "func", None), ast.Name)
                and child.func.id == "isinstance"
            ):
                has_validation = True
                break

        if not has_validation:
            issues.append(
                f"Missing input validation: function '{node.name}' has parameters "
                f"({', '.join(params)}) but no guard clauses (if/assert/raise/isinstance)"
            )

    return issues


def analyse(diff: str) -> dict:
    issues = []

    # Regex-based checks
    for label, pattern in PATTERNS:
        if pattern.search(diff):
            issues.append(label)

    # AST-based check for missing input validation
    issues.extend(_check_missing_input_validation(diff))

    return {
        "issues": issues,
        "notes": f"{len(issues)} pattern(s) matched." if issues else "No known patterns detected.",
    }
