"""
Integration test: sends buggy_login.py + task_description.txt to the /audit endpoint.
Verifies that the response flags the hardcoded credential as a HIGH security finding.
"""
import json, sys, pathlib
import requests

BASE = "http://127.0.0.1:5000"

code = pathlib.Path("../sample_code/buggy_login.py").read_text()
task = pathlib.Path("../sample_code/task_description.txt").read_text().strip()

payload = {"task": task, "code": code}
r = requests.post(f"{BASE}/audit", json=payload, timeout=15)

print(f"Status: {r.status_code}")
data = r.json()
print(json.dumps(data, indent=2))

# Assertions
assert r.status_code == 200, "Expected 200"
assert data["status"] == "RISKY", f"Expected RISKY, got {data['status']}"
assert data["security"] < 100, f"Expected security < 100, got {data['security']}"

high_findings = [f for f in data["findings"] if f["severity"] == "HIGH"]
assert high_findings, "Expected at least one HIGH security finding"
assert any("password" in f["title"].lower() or "secret" in f["title"].lower()
           for f in high_findings), "Expected a hardcoded-password finding"

print("\nAll assertions passed -- hardcoded credential correctly detected.")
