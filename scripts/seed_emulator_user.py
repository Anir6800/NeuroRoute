"""Create (or update) a TEST user in the local Firebase Auth emulator and set its `role` claim.

Usage (emulator must be running; run from repo root):
    .venv\\Scripts\\python scripts\\seed_emulator_user.py [email] [password] [role]
Emulator-only: refuses any non-loopback host. Credentials here are throwaway test values.
"""
import os
import sys

import firebase_admin
from firebase_admin import auth

HOST = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
PROJECT = "demo-neuroroute"


def main(argv: list[str]) -> int:
    email = argv[1] if len(argv) > 1 else "dev@neuroroute.test"
    password = argv[2] if len(argv) > 2 else "devpass123"
    role = argv[3] if len(argv) > 3 else "researcher"
    if HOST.rpartition(":")[0] not in ("127.0.0.1", "localhost", "::1"):
        print("refusing: emulator host must be loopback", file=sys.stderr)
        return 2
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = HOST
    app = firebase_admin.initialize_app(options={"projectId": PROJECT})
    try:
        user = auth.get_user_by_email(email, app=app)
    except auth.UserNotFoundError:
        user = auth.create_user(email=email, password=password, app=app)
    auth.set_custom_user_claims(user.uid, {"role": role}, app=app)
    print(f"seeded {email} uid={user.uid} role={role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
