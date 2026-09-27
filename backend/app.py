"""
CodeAuditor AI — Flask entry point
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from coordinator.coordinator import run_audit

load_dotenv()

app = Flask(__name__)
CORS(app)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/audit", methods=["POST"])
def audit():
    body = request.get_json(force=True)

    # Accept both "code"/"task" (frontend) and "diff"/"requirement" (API/CLI)
    diff = (body.get("code") or body.get("diff") or "").strip()
    requirement = (body.get("task") or body.get("requirement") or "").strip()

    if not diff:
        return jsonify({"error": "Missing required field: code (or diff)"}), 400

    result = run_audit(diff=diff, requirement=requirement)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
