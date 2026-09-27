import styles from './AuditResults.module.css'

const STATUS_META = {
  SAFE:    { label: 'SAFE',    color: 'green'  },
  CAUTION: { label: 'CAUTION', color: 'yellow' },
  RISKY:   { label: 'RISKY',   color: 'red'    },
}

const SEVERITY_ORDER = { HIGH: 0, MEDIUM: 1, LOW: 2 }

function TrustGauge({ score, status }) {
  const meta = STATUS_META[status] || STATUS_META.CAUTION
  return (
    <div className={styles.trustRow}>
      <div className={styles.scoreBlock}>
        <span className={styles.scoreNumber}>{score}</span>
        <span className={styles.scoreLabel}>/100</span>
      </div>
      <div className={styles.gaugeBar} role="progressbar" aria-valuenow={score} aria-valuemin={0} aria-valuemax={100} aria-label={`Trust score ${score} out of 100`}>
        <div
          className={`${styles.gaugeFill} ${styles[`gauge_${meta.color}`]}`}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className={`${styles.statusBadge} ${styles[`status_${meta.color}`]}`}>
        {meta.label}
      </span>
    </div>
  )
}

function MetricRow({ label, value, unit = '%', colorize = true }) {
  const color = colorize
    ? value >= 75 ? 'green' : value >= 50 ? 'yellow' : 'red'
    : 'neutral'
  return (
    <div className={styles.metricRow}>
      <span className={styles.metricLabel}>{label}</span>
      <span className={`${styles.metricValue} ${styles[`metric_${color}`]}`}>
        {value}{unit}
      </span>
    </div>
  )
}

function ImpactRow({ impact }) {
  const color = { LOW: 'green', MEDIUM: 'yellow', HIGH: 'red', CRITICAL: 'red' }[impact] || 'neutral'
  return (
    <div className={styles.metricRow}>
      <span className={styles.metricLabel}>Impact</span>
      <span className={`${styles.metricValue} ${styles[`metric_${color}`]}`}>{impact}</span>
    </div>
  )
}

function FindingItem({ finding }) {
  const sev = finding.severity
  const colorMap = { HIGH: 'red', MEDIUM: 'yellow', LOW: 'green' }
  const color = colorMap[sev] || 'neutral'
  return (
    <li className={styles.finding}>
      <div className={styles.findingHeader}>
        <span className={`${styles.severityTag} ${styles[`sev_${color}`]}`}>{sev}</span>
        <span className={styles.findingTitle}>{finding.title}</span>
        {finding.line != null && (
          <span className={styles.lineRef}>:{finding.line}</span>
        )}
      </div>
      <p className={styles.findingDesc}>{finding.description}</p>
    </li>
  )
}

export default function AuditResults({ result, onReset }) {
  if (!result) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon} aria-hidden="true">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
        </div>
        <p className={styles.emptyTitle}>No report yet</p>
        <p className={styles.emptyBody}>
          Paste your code and describe the requirement, then click Audit Code.
        </p>
      </div>
    )
  }

  const sortedFindings = [...result.findings].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
  )

  return (
    <div className={styles.results}>
      <div className={styles.resultsHeader}>
        <span className={styles.resultsTitle}>Audit report</span>
        <button className={styles.resetBtn} onClick={onReset} type="button">
          New audit
        </button>
      </div>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Trust score</h3>
        <TrustGauge score={result.trustScore} status={result.status} />
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Metrics</h3>
        <div className={styles.metricsTable}>
          <MetricRow label="Requirement match" value={result.requirementMatch} />
          <MetricRow label="Security" value={result.security} />
          <ImpactRow impact={result.impact} />
        </div>
      </section>

      <section className={styles.section}>
        <h3 className={styles.sectionTitle}>Summary</h3>
        <p className={styles.summary}>{result.summary}</p>
      </section>

      {sortedFindings.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>
            Findings
            <span className={styles.findingCount}>{sortedFindings.length}</span>
          </h3>
          <ul className={styles.findingsList}>
            {sortedFindings.map((f, i) => (
              <FindingItem key={i} finding={f} />
            ))}
          </ul>
        </section>
      )}

      {result.recommendations.length > 0 && (
        <section className={styles.section}>
          <h3 className={styles.sectionTitle}>Recommendations</h3>
          <ol className={styles.recList}>
            {result.recommendations.map((r, i) => (
              <li key={i} className={styles.recItem}>{r}</li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}
