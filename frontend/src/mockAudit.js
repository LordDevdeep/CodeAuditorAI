/**
 * Mock audit result — replace this with a real API call to the Flask backend.
 *
 * Shape matches the contract expected by AuditResults component:
 * {
 *   trustScore: number,          // 0–100
 *   status: 'SAFE'|'CAUTION'|'RISKY',
 *   requirementMatch: number,    // 0–100 percent
 *   security: number,            // 0–100 percent
 *   impact: 'LOW'|'MEDIUM'|'HIGH'|'CRITICAL',
 *   summary: string,
 *   findings: Array<{
 *     severity: 'HIGH'|'MEDIUM'|'LOW',
 *     title: string,
 *     description: string,
 *     line: number|null,
 *   }>,
 *   recommendations: string[],
 * }
 */

export function getMockAuditResult(language) {
  // Deterministic sample — not randomised so results feel consistent during demos
  return {
    trustScore: 61,
    status: 'CAUTION',
    requirementMatch: 78,
    security: 54,
    impact: 'MEDIUM',
    summary:
      'The submitted code partially satisfies the stated requirements but contains several security and correctness concerns that should be addressed before production use.',
    findings: [
      {
        severity: 'HIGH',
        title: 'SQL Injection via unsanitised input',
        description:
          'User-controlled data is interpolated directly into a SQL query string without parameterisation. An attacker can manipulate the query to exfiltrate or modify arbitrary data.',
        line: 14,
      },
      {
        severity: 'HIGH',
        title: 'Hardcoded secret key',
        description:
          'A cryptographic secret or API key appears to be embedded in the source code. Secrets must be loaded from environment variables or a secrets manager, never committed to source.',
        line: 3,
      },
      {
        severity: 'MEDIUM',
        title: 'Missing authentication check on sensitive endpoint',
        description:
          'The function modifies persistent state but does not verify caller identity or authorisation level before proceeding.',
        line: 27,
      },
      {
        severity: 'MEDIUM',
        title: 'Unhandled exception leaks stack trace',
        description:
          'Caught exceptions are re-raised or printed to the response body, exposing internal paths and library versions to untrusted clients.',
        line: 41,
      },
      {
        severity: 'LOW',
        title: 'Requirement gap — pagination not implemented',
        description:
          'The stated requirement mentions paginated results, but the implementation returns an unbounded list which may cause memory pressure under load.',
        line: null,
      },
    ],
    recommendations: [
      'Replace string-interpolated SQL with parameterised queries or an ORM.',
      'Move secrets to environment variables and rotate the exposed key immediately.',
      'Add an authentication/authorisation middleware before any state-mutating route.',
      'Return generic error messages to clients; log full stack traces server-side only.',
      'Implement cursor- or offset-based pagination as specified in the requirements.',
    ],
  }
}

/** Simulates the latency of a real API call */
export function runAudit(task, code, language) {
  return new Promise((resolve) => {
    setTimeout(() => resolve(getMockAuditResult(language)), 1800)
  })
}
