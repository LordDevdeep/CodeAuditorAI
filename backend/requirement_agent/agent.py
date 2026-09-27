"""
Requirement Agent — checks whether the generated code fulfils the stated task.

Strategy
--------
1. If WATSONX_API_KEY and WATSONX_PROJECT_ID are present in the environment,
   the agent calls IBM watsonx.ai (ibm/granite-3-8b-instruct) with a structured
   prompt and parses the model's JSON verdict.
2. If credentials are absent it falls back to a heuristic analyser that is
   significantly smarter than a raw keyword overlap:
     - strips diff noise (+/-/@@) before comparing
     - ignores common stop-words
     - requires ≥50 % of meaningful requirement tokens to appear in the code

Return shape (unchanged — coordinator compatible)
-------------------------------------------------
{
    "met":   bool,
    "notes": str   # short human-readable explanation / mismatch description
}
"""

from __future__ import annotations

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stop-words to ignore during heuristic analysis
# ---------------------------------------------------------------------------
_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "that", "this", "these",
    "those", "it", "its", "as", "if", "so", "not", "no", "any", "all",
    "each", "every", "both", "either", "neither", "i", "we", "you", "they",
    "he", "she", "make", "ensure", "implement", "code", "change", "add",
    "create", "use", "using", "also", "when", "where", "which", "who",
    "how", "what", "please", "need", "must",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_added_code(diff: str) -> str:
    """Return only the added/context lines of a unified diff, lowercased."""
    lines = []
    for line in diff.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("-"):
            continue  # skip removed lines — we only care about what IS there
        lines.append(line.lstrip("+").strip())
    return " ".join(lines).lower()


def _meaningful_tokens(text: str) -> set[str]:
    """Lowercase identifier-style tokens, stop-words and short tokens removed."""
    raw = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    return {t for t in raw if len(t) > 2 and t not in _STOP_WORDS}


# ---------------------------------------------------------------------------
# Heuristic fallback (no LLM credentials)
# ---------------------------------------------------------------------------

def _heuristic_analyse(code_text: str, requirement: str) -> dict:
    """
    Smarter heuristic for when no LLM credentials are available.

    Requires ≥50 % of meaningful requirement tokens to appear in the added
    code; reports exactly which terms are missing so the developer knows
    what to look for.
    """
    req_tokens  = _meaningful_tokens(requirement)
    code_tokens = _meaningful_tokens(code_text)

    if not req_tokens:
        return {"met": True, "notes": "Requirement text is empty after filtering — skipping check."}

    matched  = req_tokens & code_tokens
    missing  = req_tokens - code_tokens
    coverage = len(matched) / len(req_tokens)

    # Pass threshold: at least half of the meaningful requirement words must
    # appear somewhere in the new code.
    met = coverage >= 0.50

    if met:
        notes = (
            f"PASS ({coverage:.0%} of requirement terms found in code). "
            f"Matched: {', '.join(sorted(matched))}."
        )
    else:
        notes = (
            f"FAIL ({coverage:.0%} coverage — below 50 % threshold). "
            f"Present: {', '.join(sorted(matched)) or 'none'}. "
            f"Missing from code: {', '.join(sorted(missing))}."
        )

    return {"met": met, "notes": notes}


# ---------------------------------------------------------------------------
# IBM watsonx.ai implementation
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
You are a strict code-review assistant. A developer was given a task and produced \
the code shown below. Decide whether the code fully fulfils the task.

## Task description
{requirement}

## Code / diff (added lines only)
{code}

## Instructions
Reply with ONLY a JSON object — no markdown fences, no extra text — using exactly \
this schema:
{{
  "met": true | false,
  "notes": "<one or two sentences: what matches and what is missing>"
}}

Be strict: if behaviour described in the task is absent from the code, return false.
"""


def _watsonx_analyse(code_text: str, requirement: str) -> dict:
    """Call watsonx.ai and parse its structured JSON verdict."""
    try:
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
    except ImportError as exc:
        raise RuntimeError(
            "ibm-watsonx-ai is not installed. Run: pip install ibm-watsonx-ai"
        ) from exc

    credentials = Credentials(
        url=os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
        api_key=os.environ["WATSONX_API_KEY"],
    )
    client = APIClient(credentials=credentials)

    model = ModelInference(
        model_id=os.environ.get("WATSONX_MODEL_ID", "ibm/granite-3-8b-instruct"),
        api_client=client,
        project_id=os.environ["WATSONX_PROJECT_ID"],
        params={"max_new_tokens": 256, "temperature": 0.0},
    )

    prompt  = _PROMPT_TEMPLATE.format(
        requirement=requirement.strip(),
        code=code_text.strip()[:4000],   # guard against oversized diffs
    )
    raw     = model.generate_text(prompt=prompt)

    # Strip accidental markdown code fences the model may add
    json_text = re.sub(r"```[a-z]*\n?|```", "", raw).strip()
    verdict   = json.loads(json_text)

    return {
        "met":   bool(verdict.get("met", False)),
        "notes": str(verdict.get("notes", "No explanation returned by model.")),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse(diff: str, requirement: str) -> dict:
    """
    Check whether *diff* (the generated code) satisfies *requirement* (the task).

    Uses watsonx.ai when WATSONX_API_KEY + WATSONX_PROJECT_ID env vars are set;
    falls back to the heuristic analyser otherwise.
    """
    if not requirement:
        return {"met": True, "notes": "No requirement provided — skipping check."}

    code_text = _extract_added_code(diff)

    if os.environ.get("WATSONX_API_KEY") and os.environ.get("WATSONX_PROJECT_ID"):
        try:
            return _watsonx_analyse(code_text, requirement)
        except Exception as exc:          # noqa: BLE001
            logger.warning("watsonx call failed, falling back to heuristic: %s", exc)

    return _heuristic_analyse(code_text, requirement)
