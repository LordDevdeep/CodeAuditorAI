"""
Coordinator — calls all agents and aggregates their results into a
single risk report.
"""

from requirement_agent.agent import analyse as requirement_analyse
from security_agent.agent import analyse as security_analyse
from impact_agent.agent import analyse as impact_analyse


def run_audit(diff: str, requirement: str) -> dict:
    req_result = requirement_analyse(diff=diff, requirement=requirement)
    sec_result = security_analyse(diff=diff)
    imp_result = impact_analyse(diff=diff)

    # Simple risk score: start at 0, add points for each issue found.
    score = 0
    if not req_result.get("met"):
        score += 3
    score += len(sec_result.get("issues", [])) * 3
    if imp_result.get("risk") == "high":
        score += 4
    elif imp_result.get("risk") == "medium":
        score += 2

    score = min(score, 10)  # cap at 10

    return {
        "risk_score": score,
        "summary": _build_summary(score, req_result, sec_result, imp_result),
        "agents": {
            "requirement": req_result,
            "security": sec_result,
            "impact": imp_result,
        },
    }


def _build_summary(score, req, sec, imp) -> str:
    parts = []
    if not req.get("met"):
        parts.append("Requirement not fully met.")
    if sec.get("issues"):
        parts.append(f"{len(sec['issues'])} security issue(s) found.")
    parts.append(f"Impact: {imp.get('risk', 'unknown')}.")
    parts.append(f"Overall risk score: {score}/10.")
    return " ".join(parts)
