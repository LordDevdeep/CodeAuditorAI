"""
Impact Agent — static analysis of the blast radius when a target function
or file is changed.

Public API
----------
analyse(target, files) -> dict
    target : str
        The function name OR file path/name being changed.
    files  : dict[str, str]
        Mapping of {relative_path: file_contents} for the whole codebase.

Returns a structured result:
{
    "agent": "impact",
    "verdict": "SAFE" | "CAUTION" | "RISKY",
    "score": 0-100,
    "affected_files": [...],
    "affected_components": [...],
    "findings": [...],
    "summary": "..."
}

Legacy shim
-----------
analyse(diff)   (keyword-only, for backward compatibility with the coordinator)
    Falls back to the original diff-based heuristic so the coordinator still works.
"""

import os
import re


# ---------------------------------------------------------------------------
# Legacy diff-based heuristic (keeps the coordinator working unchanged)
# ---------------------------------------------------------------------------

def _analyse_diff(diff: str) -> dict:
    """Original stub logic, preserved so the coordinator is not broken."""
    changed_files = re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)
    added_lines = len(re.findall(r"^\+(?!\+\+)", diff, re.MULTILINE))
    removed_lines = len(re.findall(r"^-(?!--)", diff, re.MULTILINE))
    total_changes = added_lines + removed_lines

    if total_changes > 100 or len(changed_files) > 5:
        risk = "high"
    elif total_changes > 30 or len(changed_files) > 2:
        risk = "medium"
    else:
        risk = "low"

    return {
        "files_changed": changed_files,
        "lines_added": added_lines,
        "lines_removed": removed_lines,
        "risk": risk,
        "notes": (
            f"{len(changed_files)} file(s), {total_changes} line(s) changed "
            f"-> {risk} impact."
        ),
    }


# ---------------------------------------------------------------------------
# Helpers for static analysis
# ---------------------------------------------------------------------------

# File extensions considered source code
_SOURCE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cs", ".go",
    ".rb", ".php", ".cpp", ".c", ".h", ".rs", ".kt", ".swift",
}

# File extensions considered documentation
_DOC_EXTS = {".md", ".rst", ".txt", ".adoc", ".mdx"}

# Prefixes/substrings that suggest a test file
_TEST_INDICATORS = ("test_", "_test", "tests/", "test/", "spec/", ".spec.", ".test.")


def _is_source(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _SOURCE_EXTS


def _is_doc(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _DOC_EXTS


def _is_test(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    return any(ind in lower for ind in _TEST_INDICATORS)


def _target_basename(target: str) -> str:
    """Return the bare file name without extension, or the function name."""
    base = os.path.basename(target)
    return os.path.splitext(base)[0] if "." in base else base


def _build_import_patterns(target: str):
    """
    Build a list of regex patterns that would represent an import of *target*.
    Handles Python, JS/TS, and generic 'require/include' styles.
    """
    base = _target_basename(target)
    patterns = [
        # Python: from <base> import / import <base>
        rf"\bfrom\s+[\w.]*{re.escape(base)}[\w.]*\s+import\b",
        rf"\bimport\s+[\w.]*{re.escape(base)}[\w.]*\b",
        # JS/TS: require('...base...') or import ... from '...base...'
        rf"require\(['\"].*{re.escape(base)}.*['\"]\)",
        rf"from\s+['\"].*{re.escape(base)}.*['\"]",
        # Generic include/require
        rf"include\s+['\"].*{re.escape(base)}.*['\"]",
    ]
    return [re.compile(p) for p in patterns]


def _build_call_patterns(func_name: str):
    """
    Patterns that suggest the function is being called or referenced.
    Only meaningful when target looks like a plain function name (no ext).
    """
    if "." in os.path.basename(func_name):
        # It's a file target, not a plain function name
        return []
    name = _target_basename(func_name)
    return [
        re.compile(rf"\b{re.escape(name)}\s*\("),         # call: name(
        re.compile(rf"\b{re.escape(name)}\s*="),           # assignment alias
        re.compile(rf"['\"].*{re.escape(name)}.*['\"]"),   # string reference
    ]


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _analyse_target(target: str, files: dict) -> dict:
    """
    Walk every file in `files` and collect:
    - files that import the target file/module
    - files that call/use the target function
    - test files that reference the target
    - documentation files that mention the target
    """
    import_pats = _build_import_patterns(target)
    call_pats = _build_call_patterns(target)
    base = _target_basename(target)

    affected_files = []
    affected_components = []
    findings = []

    # Normalise the target path for self-exclusion
    norm_target = target.replace("\\", "/").lstrip("./")

    for path, content in files.items():
        norm_path = path.replace("\\", "/").lstrip("./")

        # Skip the target file itself
        if norm_path == norm_target or os.path.splitext(norm_path)[0] == os.path.splitext(norm_target)[0]:
            continue

        hit_reasons = []

        # 1. Import / include detection
        for pat in import_pats:
            if pat.search(content):
                hit_reasons.append("imports target")
                break

        # 2. Call / usage detection (only for function-like targets)
        if call_pats:
            for pat in call_pats:
                if pat.search(content):
                    if "calls/uses target" not in hit_reasons:
                        hit_reasons.append("calls/uses target")
                    break

        # 3. Plain name mention (catch-all for any reference)
        if not hit_reasons and re.search(rf"\b{re.escape(base)}\b", content):
            hit_reasons.append("references target by name")

        if not hit_reasons:
            continue

        affected_files.append(path)

        # Classify
        if _is_test(path):
            finding_type = "test"
            affected_components.append(f"test:{path}")
            for reason in hit_reasons:
                findings.append(f"[test] {path} — {reason}")
        elif _is_doc(path):
            finding_type = "doc"
            affected_components.append(f"doc:{path}")
            for reason in hit_reasons:
                findings.append(f"[doc] {path} — {reason}")
        elif _is_source(path):
            finding_type = "source"
            affected_components.append(f"source:{path}")
            for reason in hit_reasons:
                findings.append(f"[source] {path} — {reason}")
        else:
            finding_type = "other"
            affected_components.append(f"other:{path}")
            for reason in hit_reasons:
                findings.append(f"[other] {path} — {reason}")

    return {
        "affected_files": affected_files,
        "affected_components": affected_components,
        "findings": findings,
    }


def _score_and_verdict(affected_files, findings):
    """
    Derive a 0-100 score and SAFE/CAUTION/RISKY verdict.

    Scoring weights:
    - Each source file that imports/calls: 10 pts
    - Each test file: 8 pts
    - Each doc file: 3 pts
    - Each other file: 2 pts
    """
    score = 0
    for comp in findings:  # findings already classified
        if comp.startswith("[source]"):
            score += 10
        elif comp.startswith("[test]"):
            score += 8
        elif comp.startswith("[doc]"):
            score += 3
        else:
            score += 2

    score = min(score, 100)

    if score == 0:
        verdict = "SAFE"
    elif score <= 30:
        verdict = "CAUTION"
    else:
        verdict = "RISKY"

    return score, verdict


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyse(target: str = None, files: dict = None, diff: str = None) -> dict:
    """
    analyse(target, files)  -> structured impact result (new interface)
    analyse(diff=diff)      -> legacy diff-based result (coordinator compat)

    Parameters
    ----------
    target : str, optional
        Function name or file path being changed.
    files  : dict[str, str], optional
        {relative_path: file_contents} map of the codebase.
    diff   : str, optional
        Raw unified diff string (legacy mode).
    """
    # Legacy mode — coordinator passes only diff=
    if diff is not None and target is None:
        return _analyse_diff(diff)

    if not target:
        return {
            "agent": "impact",
            "verdict": "SAFE",
            "score": 0,
            "affected_files": [],
            "affected_components": [],
            "findings": [],
            "summary": "No target specified.",
        }

    files = files or {}
    result = _analyse_target(target, files)
    score, verdict = _score_and_verdict(result["affected_files"], result["findings"])

    n = len(result["affected_files"])
    summary = (
        f"Target '{target}' has {n} dependent file(s) detected. "
        f"Verdict: {verdict} (score {score}/100)."
    )

    return {
        "agent": "impact",
        "verdict": verdict,
        "score": score,
        "affected_files": result["affected_files"],
        "affected_components": result["affected_components"],
        "findings": result["findings"],
        "summary": summary,
    }
