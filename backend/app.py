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

    diff = body.get("diff", "").strip()
    requirement = body.get("requirement", "").strip()

    if not diff:
        return jsonify({"error": "Missing required field: diff"}), 400

    result = run_audit(diff=diff, requirement=requirement)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
