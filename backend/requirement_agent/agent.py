"""
Requirement Agent — checks whether the diff satisfies the stated requirement.

MVP stub: performs a naive keyword-overlap check.
Replace the body of `analyse()` with an LLM call (e.g. watsonx) for the real thing.
"""


def analyse(diff: str, requirement: str) -> dict:
    if not requirement:
        return {"met": True, "notes": "No requirement provided — skipping check."}

    # Naive heuristic: look for overlapping meaningful words.
    req_words = set(requirement.lower().split())
    diff_words = set(diff.lower().split())
    overlap = req_words & diff_words

    met = len(overlap) >= 1
    return {
        "met": met,
        "notes": (
            f"Keyword overlap: {sorted(overlap)}"
            if overlap
            else "No keyword overlap between requirement and diff."
        ),
    }
