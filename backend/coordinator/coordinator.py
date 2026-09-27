"""
Coordinator — calls all agents and aggregates their results into a
single risk report shaped to match the frontend AuditResults component.

Frontend expects:
{
    trustScore:        number (0-100),
    status:            "SAFE" | "CAUTION" | "RISKY",
    requirementMatch:  number (0-100),
    security:          number (0-100),
    impact:            "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
    summary:           string,
    findings: [{
        severity:    "HIGH" | "MEDIUM" | "LOW",
        title:       string,
        description: string,
        line:        number | null,
    }],
    recommendations: string[],
}
"""

from requirement_agent.agent import analyse as requirement_analyse
from security_agent.agent import analyse as security_analyse
from impact_agent.agent import analyse as impact_analyse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _overall_status(req_verdict: str, sec_verdict: str) -> str:
    """Map agent verdicts to a single SAFE / CAUTION / RISKY status."""
    verdicts = {req_verdict, sec_verdict}
    if "RISKY" in verdicts or "FAIL" in verdicts:
        return "RISKY"
    if "CAUTION" in verdicts:
        return "CAUTION"
    return "SAFE"


def _impact_label(risk: str) -> str:
    """Translate legacy diff-based risk string to frontend label."""
    mapping = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH"}
    return mapping.get(risk.lower(), "MEDIUM")


def _trust_score(req_score: int, sec_score: int) -> int:
    """Average the two meaningful scores (requirement + security)."""
    return round((req_score + sec_score) / 2)


def _collect_findings(sec_result: dict, req_result: dict) -> list[dict]:
    """Build a unified findings list from both agents."""
    findings = []

    # Security findings — already have the right shape
    for f in sec_result.get("findings", []):
        findings.append({
            "severity": f["severity"],
            "title": f["title"],
            "description": f["description"],
            "line": f.get("line_number"),
        })

    # Requirement findings — text strings, rendered as LOW findings
    for text in req_result.get("findings", []):
        findings.append({
            "severity": "LOW",
            "title": "Requirement gap",
            "description": text,
            "line": None,
        })

    return findings


def _collect_recommendations(sec_result: dict, req_result: dict) -> list[str]:
    """Gather unique recommendations from both agents."""
    seen: set[str] = set()
    recs = []

    for f in sec_result.get("findings", []):
        rec = f.get("recommendation", "")
        if rec and rec not in seen:
            seen.add(rec)
            recs.append(rec)

    for miss in req_result.get("missing_requirements", []):
        if miss not in seen:
            seen.add(miss)
            recs.append(miss)

    return recs


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_audit(diff: str, requirement: str) -> dict:
    req_result = requirement_analyse(diff=diff, requirement=requirement)
    sec_result = security_analyse(diff=diff)
    imp_result = impact_analyse(diff=diff)

    req_score = req_result.get("score", 100)
    sec_score = sec_result.get("score", 100)

    req_verdict = req_result.get("verdict", "PASS")
    sec_verdict = sec_result.get("verdict", "PASS")

    status = _overall_status(req_verdict, sec_verdict)
    trust = _trust_score(req_score, sec_score)

    impact_risk = imp_result.get("risk", "low")
    impact = _impact_label(impact_risk)

    findings = _collect_findings(sec_result, req_result)
    recommendations = _collect_recommendations(sec_result, req_result)

    # Build a human-readable summary
    sec_summary = sec_result.get("summary", "")
    req_summary = req_result.get("summary", "")
    if sec_summary and req_summary:
        summary = f"{req_summary} {sec_summary}"
    else:
        summary = sec_summary or req_summary or "Audit complete."

    return {
        "trustScore":       trust,
        "status":           status,
        "requirementMatch": req_score,
        "security":         sec_score,
        "impact":           impact,
        "summary":          summary,
        "findings":         findings,
        "recommendations":  recommendations,
    }
