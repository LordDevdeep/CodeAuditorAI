"""
Coordinator — calls all agents and aggregates their results into a
single risk report.

Each agent is normalised to {"status": "pass"|"fail"|"risky", "message": str}
before being combined into the final report.
"""

from requirement_agent.agent import analyse as requirement_analyse
from security_agent.agent import analyse as security_analyse
from impact_agent.agent import analyse as impact_analyse


# ---------------------------------------------------------------------------
# Normalisation helpers
# Each function converts an agent's native output to the canonical schema.
# ---------------------------------------------------------------------------

def _normalise_requirement(result: dict) -> dict:
    """Requirement agent returns {"met": bool, "notes": str}."""
    if result.get("met", True):
        return {"status": "pass", "message": result.get("notes", "Requirement met.")}
    return {"status": "fail", "message": result.get("notes", "Requirement not met.")}


def _normalise_security(result: dict) -> dict:
    """Security agent returns {"issues": list, "notes": str}."""
    issues = result.get("issues", [])
    if not issues:
        return {"status": "pass", "message": result.get("notes", "No issues found.")}
    return {
        "status": "fail",
        "message": result.get("notes", f"{len(issues)} issue(s) found."),
    }


def _normalise_impact(result: dict) -> dict:
    """Impact agent returns {"risk": "low"|"medium"|"high", "notes": str}."""
    risk = result.get("risk", "low")
    message = result.get("notes", f"Impact risk: {risk}.")
    if risk == "high":
        return {"status": "fail", "message": message}
    if risk == "medium":
        return {"status": "risky", "message": message}
    return {"status": "pass", "message": message}


# ---------------------------------------------------------------------------
# Verdict and trust-score logic
# ---------------------------------------------------------------------------

def _compute_verdict_and_score(agents: dict) -> tuple[str, int]:
    """
    Rules:
    - trust_score starts at 10; subtract 2 for every agent that doesn't pass.
    - overall verdict:
        "Safe"           — all three pass
        "Review Needed"  — exactly one flags an issue (fail or risky)
        "Risky"          — two or more flag an issue
    """
    non_passing = sum(
        1 for a in agents.values() if a["status"] != "pass"
    )

    trust_score = max(10 - non_passing * 2, 0)

    if non_passing == 0:
        verdict = "Safe"
    elif non_passing == 1:
        verdict = "Review Needed"
    else:
        verdict = "Risky"

    return verdict, trust_score


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_audit(diff: str, requirement: str) -> dict:
    req_result = _normalise_requirement(requirement_analyse(diff=diff, requirement=requirement))
    sec_result = _normalise_security(security_analyse(diff=diff))
    imp_result = _normalise_impact(impact_analyse(diff=diff))

    agents = {
        "requirement": req_result,
        "security": sec_result,
        "impact": imp_result,
    }

    verdict, trust_score = _compute_verdict_and_score(agents)

    return {
        "verdict": verdict,
        "trust_score": trust_score,
        "agents": agents,
    }
