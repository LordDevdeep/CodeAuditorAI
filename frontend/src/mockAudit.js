/**
 * Calls the Flask backend /audit endpoint.
 *
 * The backend returns a shape that matches AuditResults directly:
 * {
 *   trustScore: number,
 *   status: 'SAFE'|'CAUTION'|'RISKY',
 *   requirementMatch: number,
 *   security: number,
 *   impact: 'LOW'|'MEDIUM'|'HIGH'|'CRITICAL',
 *   summary: string,
 *   findings: Array<{ severity, title, description, line }>,
 *   recommendations: string[],
 * }
 */

export async function runAudit(task, code, language) {
    const response = await fetch('/api/audit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task, code, language }),
  })

  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error(err.error || `Server error ${response.status}`)
  }

  return response.json()
}
