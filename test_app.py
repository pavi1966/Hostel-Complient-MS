import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash

import app


class ComplaintApiTests(unittest.TestCase):
    def setUp(self):
        app.app.testing = True
        self.client = app.app.test_client()

    def set_user(self, user_id=7, role="student"):
        with self.client.session_transaction() as session:
            session["user"] = {"id": user_id, "name": "Rae Student", "role": role}

    def test_registration_stores_a_password_hash(self):
        with patch("app.execute_insert", return_value=12) as insert:
            response = self.client.post("/api/register", json={
                "name": "Rae Student",
                "student_id": "S12345",
                "email": "rae@example.com",
                "password": "a-strong-pass",
                "password_confirmation": "a-strong-pass",
                "hostel_block": "C",
                "room_number": "204",
            })

        self.assertEqual(response.status_code, 201)
        stored_hash = insert.call_args.args[1][3]
        self.assertNotEqual(stored_hash, "a-strong-pass")
        self.assertTrue(check_password_hash(stored_hash, "a-strong-pass"))

    def test_student_complaint_is_saved_with_their_account_id(self):
        self.set_user(user_id=7)
        with patch("app.execute_insert", return_value=44) as insert, patch("app.execute_update") as update:
            response = self.client.post("/api/complaints", json={
                "category": "Electrical",
                "title": "Light is out",
                "description": "The ceiling light is not working.",
                "hostel_block": "C",
                "room_number": "204",
            })

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json["complaint_id"].startswith("HC-"))
        self.assertEqual(insert.call_args.args[1][1], 7)
        self.assertEqual(update.call_args.args[1][1], 44)

    def test_student_complaints_are_scoped_to_their_account(self):
        self.set_user(user_id=7)
        with patch("app.query_all", return_value=[]) as query:
            response = self.client.get("/api/complaints")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(query.call_args.args[1], (7,))

    def test_student_cannot_open_warden_queue(self):
        self.set_user(role="student")
        response = self.client.get("/api/admin/complaints")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_save_unchanged_status_and_missing_ids_are_404(self):
        self.set_user(user_id=9, role="admin")
        with patch("app.execute_update", return_value=0), patch("app.query_one", return_value={"id": 44}):
            unchanged = self.client.put(
                "/api/admin/complaints/44/status", json={"status": "Pending"}
            )
        self.assertEqual(unchanged.status_code, 200)

        with patch("app.execute_update", return_value=0), patch("app.query_one", return_value=None):
            missing = self.client.put(
                "/api/admin/complaints/45/status", json={"status": "Resolved"}
            )
        self.assertEqual(missing.status_code, 404)

    def test_login_checks_hash_and_sets_session(self):
        password_hash = generate_password_hash("a-strong-pass")
        user = {
            "id": 7,
            "name": "Rae Student",
            "student_id": "S12345",
            "email": "rae@example.com",
            "password_hash": password_hash,
            "role": "student",
        }
        with patch("app.query_one", return_value=user):
            response = self.client.post("/api/login", json={
                "identifier": "S12345",
                "password": "a-strong-pass",
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["user"]["role"], "student")
        self.assertEqual(self.client.get("/api/session").json["user"]["id"], 7)

    def test_admin_has_a_separate_login_and_dashboard(self):
        password_hash = generate_password_hash("warden-pass")
        user = {
            "id": 9,
            "name": "Hostel Warden",
            "student_id": "WARDEN001",
            "email": "warden@example.com",
            "password_hash": password_hash,
            "role": "admin",
        }
        with patch("app.query_one", return_value=user):
            login = self.client.post("/api/admin/login", json={
                "identifier": "WARDEN001",
                "password": "warden-pass",
            })
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json["user"]["role"], "admin")

        with patch("app.query_one", return_value={
            "total": 4, "pending": 1, "in_progress": 1, "resolved": 2,
        }):
            dashboard = self.client.get("/api/admin/dashboard")
        self.assertEqual(dashboard.json["counts"]["in_progress"], 1)

    def test_warden_search_and_category_status_filters_are_parameterized(self):
        self.set_user(user_id=9, role="admin")
        with patch("app.query_all", return_value=[]) as query:
            response = self.client.get(
                "/api/admin/complaints?q=WARDEN001&category=Water&status=Pending"
            )
        self.assertEqual(response.status_code, 200)
        sql, values = query.call_args.args
        self.assertIn("u.student_id LIKE %s", sql)
        self.assertEqual(values, ("Water", "Pending", "%WARDEN001%", "%WARDEN001%", "%WARDEN001%", "%WARDEN001%"))

    def test_feedback_requires_resolved_owned_complaint_and_saves_rating(self):
        self.set_user(user_id=7)
        payload = {"rating": 5, "comment": "Issue was fixed quickly."}
        with patch("app.query_one", return_value={"id": 44}), patch("app.execute_insert", return_value=5) as insert:
            response = self.client.post("/api/complaints/44/feedback", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(insert.call_args.args[1], (44, 7, 5, "Issue was fixed quickly."))

        with patch("app.query_one", return_value=None):
            unavailable = self.client.post("/api/complaints/45/feedback", json=payload)
        self.assertEqual(unavailable.status_code, 400)

    def test_registration_rejects_mismatched_password_confirmation(self):
        response = self.client.post("/api/register", json={
            "name": "Rae Student", "student_id": "S12345", "email": "rae@example.com",
            "password": "a-strong-pass", "password_confirmation": "a-different-pass",
            "hostel_block": "C", "room_number": "204",
        })
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
