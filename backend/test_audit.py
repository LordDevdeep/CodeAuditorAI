import json
import requests

url = "http://127.0.0.1:5000/audit"

payload = {
    "diff": "def login(username, password):\n    if username == 'admin' and password == '12345':\n        return True\n    return False",
    "requirement": "validate user email and password before login"
}

response = requests.post(url, json=payload)

print(f"Status Code: {response.status_code}")
print("Response:")
print(json.dumps(response.json(), indent=2))
