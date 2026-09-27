# CodeAuditor AI

> Audit AI-generated code changes for risk before you commit them.

CodeAuditor AI is a hackathon project that sits between your AI coding assistant and your Git commit. It analyses a proposed diff and surfaces three categories of risk so developers can make an informed decision before merging.

---

## 🔍 What it does

| Agent | Responsibility |
|---|---|
| **Requirement Agent** | Checks whether the change actually fulfils the stated requirement or ticket description |
| **Security Agent** | Scans for common vulnerabilities — hardcoded secrets, injection risks, insecure defaults |
| **Impact Agent** | Identifies blast radius — which files, functions, or services are affected |
| **Coordinator** | Aggregates the three agent reports into a single risk score and summary |

---

## 🗂️ Project structure

```
CodeAuditorAI/
├── backend/
│   ├── app.py                  # Flask entry point
│   ├── requirements.txt        # Python dependencies
│   ├── coordinator/            # Aggregates agent results → final report
│   ├── requirement_agent/      # Requirement-coverage analysis
│   ├── security_agent/         # Security vulnerability scan
│   └── impact_agent/           # Change impact analysis
├── frontend/                   # (UI — TBD)
├── sample_code/                # Example diffs for demo / testing
└── bob_sessions/               # Saved Bob AI session logs
```

---

## 🚀 Quick start

### Prerequisites
- Python 3.10+
- pip

### Run the backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

The API will be available at `http://localhost:5000`.

### API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/audit` | Submit a diff for full audit |

**Example request:**

```bash
curl -X POST http://localhost:5000/audit \
  -H "Content-Type: application/json" \
  -d '{"diff": "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n+import os\n+password = \"hunter2\"", "requirement": "Add env-var support"}'
```

**Example response:**

```json
{
  "risk_score": 8,
  "summary": "Hardcoded password detected. Requirement partially met.",
  "agents": {
    "requirement": { "met": false, "notes": "Requirement calls for env-var; change uses a literal." },
    "security":   { "issues": ["Hardcoded credential on line 2"] },
    "impact":     { "files_changed": ["app.py"], "risk": "low" }
  }
}
```

---

## 🔒 Security reminder

- Never commit `.env` or credentials — see [SECURITY.MD](SECURITY.MD)
- All API keys must go in a `.env` file (already git-ignored)

---

## 🛠️ Tech stack

- **Backend:** Python, Flask
- **AI / LLM:** IBM watsonx (planned)
- **Frontend:** TBD (plain HTML or React)

---

## 👥 Team

Built for the IBM Hackathon.
