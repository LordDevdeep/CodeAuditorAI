import styles from './AuditForm.module.css'

const LANGUAGES = [
  'Python',
  'JavaScript',
  'TypeScript',
  'Java',
  'C#',
  'C++',
  'Go',
  'Rust',
  'PHP',
  'Ruby',
  'Swift',
  'Kotlin',
  'Other',
]

export default function AuditForm({ task, code, language, onTaskChange, onCodeChange, onLanguageChange, onSubmit, loading }) {
  return (
    <form className={styles.form} onSubmit={onSubmit} noValidate>
      <div className={styles.field}>
        <label htmlFor="task" className={styles.label}>
          Task / requirement
          <span className={styles.hint}>What is this code supposed to do?</span>
        </label>
        <textarea
          id="task"
          className={styles.textarea}
          value={task}
          onChange={(e) => onTaskChange(e.target.value)}
          placeholder="e.g. Build a REST endpoint that accepts a username and password, authenticates against the users table, and returns a signed JWT on success."
          rows={3}
          disabled={loading}
        />
      </div>

      <div className={styles.field}>
        <div className={`${styles.codeEditorWrap}${loading ? ' ' + styles.disabled : ''}`}>
          <div className={styles.editorBar}>
            <span className={styles.editorBarLabel}>AI-generated code</span>
            <div className={styles.editorBarRight}>
              <span className={styles.langDot} aria-hidden="true" />
              <label htmlFor="language" className={styles.srOnly}>Language</label>
              <select
                id="language"
                className={styles.select}
                value={language}
                onChange={(e) => onLanguageChange(e.target.value)}
                disabled={loading}
              >
                {LANGUAGES.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </div>
          </div>
          <textarea
            id="code"
            className={styles.codeArea}
            value={code}
            onChange={(e) => onCodeChange(e.target.value)}
            placeholder={`# Paste ${language} code here…`}
            rows={18}
            spellCheck={false}
            disabled={loading}
          />
        </div>
      </div>

      <div className={styles.formActions}>
        <button
          type="submit"
          className={styles.button}
          disabled={loading}
          aria-busy={loading}
        >
          {loading ? (
            <>
              <span className={styles.spinner} aria-hidden="true" />
              Auditing…
            </>
          ) : (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <polyline points="9 12 11 14 15 10"/>
              </svg>
              Audit Code
            </>
          )}
        </button>
      </div>
    </form>
  )
}
