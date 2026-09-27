import { useState } from 'react'
import Header from './components/Header.jsx'
import AuditForm from './components/AuditForm.jsx'
import AuditResults from './components/AuditResults.jsx'
import { runAudit } from './mockAudit.js'
import styles from './App.module.css'

export default function App() {
  const [task, setTask] = useState('')
  const [code, setCode] = useState('')
  const [language, setLanguage] = useState('Python')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (!task.trim()) {
      setError('Please describe the task or requirement before auditing.')
      return
    }
    if (!code.trim()) {
      setError('Please paste the AI-generated code before auditing.')
      return
    }

    setLoading(true)
    setResult(null)
    try {
      const data = await runAudit(task, code, language)
      setResult(data)
    } catch (err) {
      setError('Audit failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setTask('')
    setCode('')
    setLanguage('Python')
    setResult(null)
    setError('')
  }

  return (
    <div className={styles.layout}>
      <Header />
      <main className={styles.main}>
        <div className={styles.workspace}>
          <section className={styles.leftPanel} aria-label="Audit input">
            <div className={styles.panelHeader}>
              <span className={styles.panelTitle}>Code input</span>
            </div>
            <div className={styles.panelBody}>
              {error && (
                <div className={styles.errorBanner} role="alert">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                  </svg>
                  {error}
                </div>
              )}
              <AuditForm
                task={task}
                code={code}
                language={language}
                onTaskChange={setTask}
                onCodeChange={setCode}
                onLanguageChange={setLanguage}
                onSubmit={handleSubmit}
                loading={loading}
              />
            </div>
          </section>

          <section className={styles.rightPanel} aria-label="Audit results">
            <div className={styles.panelHeader}>
              <span className={styles.panelTitle}>Audit results</span>
              {result && (
                <span className={styles.completedDot} aria-label="Audit complete" />
              )}
            </div>
            <AuditResults result={result} onReset={handleReset} />
          </section>
        </div>
      </main>
    </div>
  )
}
