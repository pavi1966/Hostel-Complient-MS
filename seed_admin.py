import os
import sys
from pathlib import Path

from werkzeug.security import generate_password_hash

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import execute_insert, initialize_database, query_one  # noqa: E402


def main():
    email = os.getenv("ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("ADMIN_PASSWORD", "")
    name = os.getenv("ADMIN_NAME", "Hostel Warden").strip()
    student_id = os.getenv("ADMIN_STUDENT_ID", "WARDEN001").strip()
    if not email or len(password) < 8 or not student_id:
        raise SystemExit("Set ADMIN_EMAIL, ADMIN_STUDENT_ID, and ADMIN_PASSWORD (at least 8 characters) first.")

    initialize_database()
    if query_one("SELECT id FROM users WHERE email = %s OR student_id = %s", (email, student_id)):
        raise SystemExit("That admin email or ID already exists. Choose different values.")
    execute_insert(
        """INSERT INTO users
           (name, student_id, email, password_hash, hostel_block, room_number, role)
           VALUES (%s, %s, %s, %s, 'Administration', 'N/A', 'admin')""",
        (name, student_id, email, generate_password_hash(password)),
    )
    print(f"Warden account created for {student_id} ({email}).")


if __name__ == "__main__":
    main()
