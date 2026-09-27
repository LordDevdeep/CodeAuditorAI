"""
Security Agent — scans the diff for common security red flags.

MVP stub: regex-based pattern matching.
Replace / extend with an LLM call or a dedicated SAST tool for the real thing.
"""

import re

# Each entry: (label, regex pattern)
PATTERNS = [
    ("Hardcoded password", r'(?i)(password|passwd|pwd)\s*=\s*["\'].+["\']'),
    ("Hardcoded API key / secret", r'(?i)(api_key|secret|token)\s*=\s*["\'].+["\']'),
    ("SQL string concatenation (possible injection)", r'(?i)(SELECT|INSERT|UPDATE|DELETE).+\+'),
    ("Use of eval()", r'\beval\s*\('),
    ("Use of exec()", r'\bexec\s*\('),
    ("Dangerous shell call", r'(?i)(os\.system|subprocess\.call|subprocess\.run)\s*\('),
]


def analyse(diff: str) -> dict:
    issues = []
    for label, pattern in PATTERNS:
        if re.search(pattern, diff):
            issues.append(label)

    return {
        "issues": issues,
        "notes": f"{len(issues)} pattern(s) matched." if issues else "No known patterns detected.",
    }
