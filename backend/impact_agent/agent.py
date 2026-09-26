"""
Impact Agent — estimates the blast radius of the diff.

MVP stub: counts changed files and lines to derive a rough risk tier.
Replace with dependency-graph analysis or an LLM call for the real thing.
"""

import re


def analyse(diff: str) -> dict:
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
        "notes": f"{len(changed_files)} file(s), {total_changes} line(s) changed → {risk} impact.",
    }
