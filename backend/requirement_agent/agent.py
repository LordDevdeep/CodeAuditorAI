"""
Requirement Agent — checks whether the generated code fulfils the stated task.

Strategy
--------
1. If WATSONX_API_KEY and WATSONX_PROJECT_ID are present in the environment,
   the agent calls IBM watsonx.ai (ibm/granite-3-8b-instruct) with a structured
   prompt and parses the model's JSON verdict.
2. If credentials are absent it falls back to a rule-based analyser that:
     - parses explicit requirements from the task description
     - checks for each requirement's presence or absence in the code
     - detects obvious contradictions (e.g. task says "do not" but code does it)
     - flags edge cases mentioned in the task that are unhandled in the code

Return shape
------------
Primary (new structured output):
{
    "agent":                "requirement",
    "verdict":              "PASS" | "CAUTION" | "FAIL",
    "score":                0–100,
    "findings":             [str, ...],
    "missing_requirements": [str, ...],
    "summary":              str
}

Coordinator-compatibility fields also present in every return value:
    "met":   bool   (True when verdict == "PASS")
    "notes": str    (same as summary)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stop-words (used only for token-level fallback helpers)
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
# Patterns that signal an edge-case / guard requirement in the task text
# ---------------------------------------------------------------------------
_EDGE_CASE_PATTERNS: list[tuple[str, list[str]]] = [
    # (task keyword,  code evidence tokens)
    (r"\bempty\b",          ["if not", "if len", "== 0", "len(", "not "]),
    (r"\bnone\b",           ["is none", "is not none", "none", "if not"]),
    (r"\bnull\b",           ["is none", "is not none", "null", "if not"]),
    (r"\bnegative\b",       ["< 0", ">= 0", "abs(", "negative"]),
    (r"\bzero\b",           ["== 0", "!= 0", "/ ", "zero", "zerodivision"]),
    (r"\bdivid",            ["zerodivisionerror", "/ ", "try", "except", "!= 0", "== 0"]),
    (r"\boverflow\b",       ["overflow", "maxsize", "try", "except"]),
    (r"\binvalid\b",        ["raise", "valueerror", "typeerror", "try", "except", "if not"]),
    (r"\berror\b",          ["raise", "try", "except", "error"]),
    (r"\bexception\b",      ["try", "except", "raise", "exception"]),
    (r"\boutput\b",         ["return", "print", "yield"]),
    (r"\breturn\b",         ["return"]),
    (r"\bsorted?\b",        ["sort", "sorted"]),
    (r"\bunique\b",         ["set(", "distinct", "unique", ".union"]),
    (r"\bcase.insensitive\b", ["lower()", "upper()", ".lower", ".upper", "casefold"]),
    (r"\bwhitespace\b",     [".strip", ".lstrip", ".rstrip", "strip()"]),
    (r"\btype\b",           ["isinstance", "type(", "typeerror"]),
    (r"\blist\b",           ["list", "[]", "append", "extend", "if not", "if len"]),
    (r"\bdict(?:ionary)?\b", ["dict", "{}", ".get(", "keys()"]),
    (r"\bfile\b",           ["open(", "with open", "file", "path"]),
    (r"\brecursive\b",      ["def ", "return", "self"]),  # recursive fn calls itself
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_code(code: str) -> str:
    """
    Strip unified-diff noise (+/-/@@) and return the meaningful code content,
    lowercased, as a single string suitable for searching.
    """
    lines = []
    for line in code.splitlines():
        if line.startswith(("---", "+++", "@@")):
            continue
        if line.startswith("-"):
            continue  # skip removed lines
        lines.append(line.lstrip("+").strip())
    return "\n".join(lines).lower()


def _tokens(text: str) -> set[str]:
    """Lowercase identifier tokens, stop-words and very short tokens removed."""
    raw = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    return {t for t in raw if len(t) > 2 and t not in _STOP_WORDS}


def _sentence_chunks(text: str) -> list[str]:
    """
    Split the requirement into individual sentences / bullet-point lines
    so we can check each obligation separately.
    """
    # Split on sentence terminators, newlines, and common list markers
    parts = re.split(r"(?:[.\n]|\band\b|\balso\b)", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _code_contains(code_lower: str, tokens: list[str]) -> bool:
    """Return True if *any* of the evidence tokens appear in the code string."""
    return any(t in code_lower for t in tokens)


# ---------------------------------------------------------------------------
# Core rule-based analysis
# ---------------------------------------------------------------------------

@dataclass
class _AnalysisResult:
    findings: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)


def _rule_based_analyse(code_lower: str, requirement: str) -> _AnalysisResult:
    result = _AnalysisResult()
    req_lower = requirement.lower()

    # ------------------------------------------------------------------
    # 1. Token-coverage check — are the core domain words present?
    #
    # We only look at "technical" tokens: identifiers that look like they
    # could appear in code (contain underscore, digits, or are > 5 chars
    # and not common English verbs/adjectives).  Pure natural-language
    # description words like "calculates", "function", "handles",
    # "returning", "safely" are excluded from the coverage check because
    # they will never appear verbatim in source code.
    # ------------------------------------------------------------------
    # Extra stop-words for coverage only (NL words that describe the task
    # but are not expected to appear in code).
    _NL_ONLY = {
        "function", "calculates", "calculate", "handles", "handle",
        "returns", "returning", "safely", "safely", "creates", "written",
        "write", "writes", "written", "provides", "provide", "generates",
        "generate", "performs", "perform", "checks", "check", "verifies",
        "verify", "computes", "compute", "builds", "build",
        "takes", "take", "accepts", "accept", "given", "produces",
        "produce", "outputs", "output", "reads", "processes", "process",
    }

    req_tokens  = _tokens(requirement) - _NL_ONLY
    code_tokens = _tokens(code_lower)
    if req_tokens:
        matched  = req_tokens & code_tokens
        absent   = req_tokens - code_tokens
        coverage = len(matched) / len(req_tokens)

        if coverage < 0.30:
            # Only add to findings (informational); do NOT add to missing
            # because token absence doesn't reliably signal a broken feature.
            result.findings.append(
                f"Low concept coverage ({coverage:.0%}): requirement terms "
                f"not found in code — {', '.join(sorted(absent))}."
            )
        elif coverage < 0.55:
            result.findings.append(
                f"Partial concept coverage ({coverage:.0%}): some requirement "
                f"terms not found — {', '.join(sorted(absent))}."
            )

    # ------------------------------------------------------------------
    # 2. Edge-case / guard checks
    #    If the task *mentions* a guard condition, verify the code handles it.
    # ------------------------------------------------------------------
    for pattern, evidence in _EDGE_CASE_PATTERNS:
        if re.search(pattern, req_lower):
            if not _code_contains(code_lower, evidence):
                label = pattern.strip(r"\b").replace("\\b", "").replace("\\", "")
                result.findings.append(
                    f"Task mentions '{label}' but no corresponding guard / "
                    f"handling found in code."
                )
                result.missing.append(
                    f"Edge-case handling for '{label}' appears to be missing."
                )

    # ------------------------------------------------------------------
    # 3. Contradiction detection — task says "do not X" but code does X
    # ------------------------------------------------------------------
    negation_phrases = re.findall(
        r"(?:do not|don'?t|never|avoid|without|no)\s+(\w+)", req_lower
    )
    for forbidden in negation_phrases:
        if len(forbidden) > 3 and forbidden not in _STOP_WORDS:
            if forbidden in code_lower:
                result.findings.append(
                    f"Possible contradiction: task says to avoid '{forbidden}' "
                    f"but the word appears in the code."
                )

    # ------------------------------------------------------------------
    # 4. Explicit functional verbs — does code contain the expected operation?
    # ------------------------------------------------------------------
    func_verb_map: list[tuple[str, list[str]]] = [
        (r"\bsort\b",       ["sort", "sorted", "order"]),
        (r"\bfilter\b",     ["filter", "if ", "comprehension", "lambda"]),
        (r"\bsearch\b",     ["find", "search", "index", "in "]),
        (r"\bencrypt\b",    ["encrypt", "cipher", "aes", "fernet", "crypto"]),
        (r"\bdecrypt\b",    ["decrypt", "decipher", "aes", "fernet", "crypto"]),
        (r"\bhash\b",       ["hash", "sha", "md5", "bcrypt", "hashlib"]),
        (r"\bvalidat\b",    ["if ", "raise", "assert", "valid", "check", "error"]),
        (r"\bpars[ei]\b",   ["parse", "json", "xml", "csv", "split", "re."]),
        (r"\bread\b",       ["read", "open", "load", "input"]),
        (r"\bwrit[ei]\b",   ["write", "open", "save", "output"]),
        (r"\bconnect\b",    ["connect", "socket", "request", "urllib", "http"]),
        (r"\baverage|mean\b", ["sum", "len", "mean", "average", "statistics"]),
        (r"\bmaximum|max\b",  ["max(", "maximum"]),
        (r"\bminimum|min\b",  ["min(", "minimum"]),
        (r"\bcount\b",      ["count", "len(", "sum("]),
        (r"\bsum\b",        ["sum(", "total", "+="]),
        (r"\breverse\b",    ["reverse", "reversed", "[::-1]"]),
        (r"\bflatten\b",    ["flatten", "chain", "extend", "comprehension"]),
        (r"\bremov[ei]\b",  ["remove", "del ", "pop(", "filter", "discard"]),
    ]
    for pattern, evidence in func_verb_map:
        if re.search(pattern, req_lower):
            if not _code_contains(code_lower, evidence):
                label = re.sub(r"\\b|\\", "", pattern).strip()
                result.findings.append(
                    f"Task requires '{label}' operation but matching "
                    f"implementation not detected in code."
                )
                result.missing.append(f"'{label}' operation appears to be missing.")

    return result


# ---------------------------------------------------------------------------
# Verdict + score calculation
# ---------------------------------------------------------------------------

def _build_verdict(result: _AnalysisResult) -> tuple[str, int]:
    """
    Derive (verdict, score) from the collected findings.

    Scoring:
      Start at 100.
      Each missing_requirement  → −15
      Each non-missing finding  → −8
    """
    n_missing  = len(result.missing)
    n_findings = len(result.findings) - n_missing  # findings not also in missing

    score = 100 - (n_missing * 15) - (max(n_findings, 0) * 8)
    score = max(0, min(100, score))

    if score >= 80:
        verdict = "PASS"
    elif score >= 50:
        verdict = "CAUTION"
    else:
        verdict = "FAIL"

    return verdict, score


# ---------------------------------------------------------------------------
# Heuristic public entrypoint (no-LLM path)
# ---------------------------------------------------------------------------

def _heuristic_analyse(code_text: str, requirement: str) -> dict:
    code_lower = _clean_code(code_text)
    result     = _rule_based_analyse(code_lower, requirement)
    verdict, score = _build_verdict(result)

    # Deduplicate while preserving order
    seen: set[str] = set()
    findings: list[str] = []
    for f in result.findings:
        if f not in seen:
            seen.add(f)
            findings.append(f)

    missing: list[str] = []
    seen_m: set[str] = set()
    for m in result.missing:
        if m not in seen_m:
            seen_m.add(m)
            missing.append(m)

    if verdict == "PASS":
        if findings:
            summary = "Code appears to satisfy the requirement with minor observations."
        else:
            summary = "All checked requirements appear to be satisfied by the code."
    elif verdict == "CAUTION":
        summary = (
            f"Code partially satisfies the requirement. "
            f"{len(missing)} item(s) may be missing or incomplete."
        )
    else:
        summary = (
            f"Code does not appear to satisfy the requirement. "
            f"{len(missing)} required element(s) missing."
        )

    return {
        # New structured output
        "agent":                "requirement",
        "verdict":              verdict,
        "score":                score,
        "findings":             findings,
        "missing_requirements": missing,
        "summary":              summary,
        # Coordinator-compatibility
        "met":   verdict == "PASS",
        "notes": summary,
    }


# ---------------------------------------------------------------------------
# IBM watsonx.ai implementation
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = """\
You are a strict code-review assistant. A developer was given a task and produced \
the code shown below. Decide whether the code fully fulfils the task.

## Task description
{requirement}

## Code (added lines only)
{code}

## Instructions
Reply with ONLY a JSON object — no markdown fences, no extra text — using exactly \
this schema:
{{
  "verdict": "PASS" | "CAUTION" | "FAIL",
  "score": <integer 0-100>,
  "findings": ["<finding 1>", ...],
  "missing_requirements": ["<missing 1>", ...],
  "summary": "<two or three sentences>"
}}

Be strict: if behaviour described in the task is absent from the code, use FAIL or CAUTION.
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
        params={"max_new_tokens": 512, "temperature": 0.0},
    )

    code_clean = _clean_code(code_text)
    prompt = _PROMPT_TEMPLATE.format(
        requirement=requirement.strip(),
        code=code_clean.strip()[:4000],
    )
    raw = model.generate_text(prompt=prompt)

    json_text = re.sub(r"```[a-z]*\n?|```", "", raw).strip()
    verdict_raw = json.loads(json_text)

    verdict = str(verdict_raw.get("verdict", "FAIL")).upper()
    if verdict not in ("PASS", "CAUTION", "FAIL"):
        verdict = "FAIL"

    score   = int(verdict_raw.get("score", 0))
    summary = str(verdict_raw.get("summary", "No explanation returned by model."))

    return {
        "agent":                "requirement",
        "verdict":              verdict,
        "score":                score,
        "findings":             list(verdict_raw.get("findings", [])),
        "missing_requirements": list(verdict_raw.get("missing_requirements", [])),
        "summary":              summary,
        # Coordinator-compatibility
        "met":   verdict == "PASS",
        "notes": summary,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse(diff: str, requirement: str) -> dict:
    """
    Check whether *diff* (the generated code) satisfies *requirement* (the task).

    Uses watsonx.ai when WATSONX_API_KEY + WATSONX_PROJECT_ID env vars are set;
    falls back to the rule-based analyser otherwise.

    Always returns a dict with keys:
        agent, verdict, score, findings, missing_requirements, summary,
        met (bool), notes (str)
    """
    if not requirement:
        return {
            "agent":                "requirement",
            "verdict":              "PASS",
            "score":                100,
            "findings":             [],
            "missing_requirements": [],
            "summary":              "No requirement provided — skipping check.",
            "met":                  True,
            "notes":                "No requirement provided — skipping check.",
        }

    if os.environ.get("WATSONX_API_KEY") and os.environ.get("WATSONX_PROJECT_ID"):
        try:
            return _watsonx_analyse(diff, requirement)
        except Exception as exc:          # noqa: BLE001
            logger.warning("watsonx call failed, falling back to heuristic: %s", exc)

    return _heuristic_analyse(diff, requirement)
