# Intentionally buggy — for audit testing only.

ADMIN_PASSWORD = "supersecret123"  # hardcoded password


def login(username, password):
    # BUG 1 (security): compares against a hardcoded password in plaintext.
    # BUG 2 (requirement): email format is never validated, despite the task
    #                      requiring it.
    if password == ADMIN_PASSWORD:
        return {"success": True, "user": username}
    return {"success": False, "user": None}


def handle_login_request(form_data):
    username = form_data.get("username")
    password = form_data.get("password")
    # BUG 3 (requirement): no check that username/password are non-empty
    #                      before passing them to login().
    return login(username, password)
