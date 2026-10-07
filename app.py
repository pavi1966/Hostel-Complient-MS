from functools import wraps
import os
from pathlib import Path
import re
from datetime import datetime
from uuid import uuid4

import mysql.connector
from mysql.connector import IntegrityError
from flask import Flask, jsonify, request, send_from_directory, session
from werkzeug.security import check_password_hash, generate_password_hash

from db import (
    DATABASE_NAME,
    connect_to_mysql,
    execute_insert,
    execute_update,
    initialize_database,
    query_all,
    query_one,
)
ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "FRONTEND"
ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR
app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "change-this-development-secret"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


def login_required(role=None):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = session.get("user")
            if not user:
                return jsonify(error="Please log in to continue."), 401
            if role and user.get("role") != role:
                return jsonify(error="You do not have permission to do that."), 403
            return view(*args, **kwargs)

        return wrapped

    return decorate


def request_data():
    return request.get_json(silent=True) or {}


@app.get("/")
def home():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/api/session")
def current_session():
    return jsonify(user=session.get("user"))


@app.get("/api/health")
def health():
    try:
        query_one("SELECT 1 AS connected")
    except mysql.connector.Error:
        return jsonify(status="running", database="unavailable"), 503
    return jsonify(status="running", database="connected", database_name=DATABASE_NAME)


@app.errorhandler(mysql.connector.Error)
def database_error(_error):
    app.logger.exception("A MySQL operation failed")
    return jsonify(error="Database unavailable. Check the MySQL server and connection settings."), 503


@app.post("/api/register")
def register():
    data = request_data()
    fields = (
        "name", "student_id", "email", "password", "password_confirmation",
        "hostel_block", "room_number",
    )
    values = {field: str(data.get(field, "")).strip() for field in fields}
    if any(not value for value in values.values()):
        return jsonify(error="Please complete every field."), 400
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", values["email"]):
        return jsonify(error="Enter a valid email address."), 400
    if len(values["password"]) < 8:
        return jsonify(error="Password must be at least 8 characters."), 400
    if values["password"] != values["password_confirmation"]:
        return jsonify(error="Passwords do not match."), 400

    try:
        user_id = execute_insert(
            """INSERT INTO users
               (name, student_id, email, password_hash, hostel_block, room_number)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                values["name"],
                values["student_id"],
                values["email"].lower(),
                generate_password_hash(values["password"]),
                values["hostel_block"],
                values["room_number"],
            ),
        )
    except IntegrityError:
        return jsonify(error="That student ID or email is already registered."), 409

    return jsonify(message="Your account has been created.", user_id=user_id), 201


@app.post("/api/login")
def login():
    data = request_data()
    identifier = str(data.get("identifier", data.get("email", ""))).strip()
    password = str(data.get("password", ""))
    user = query_one(
        """SELECT id, name, student_id, email, password_hash, role
           FROM users WHERE (student_id = %s OR email = %s) AND role = 'student'""",
        (identifier, identifier.lower()),
    )
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Student ID/email or password is incorrect."), 401

    session.clear()
    session["user"] = {
        "id": user["id"],
        "name": user["name"],
        "student_id": user["student_id"],
        "email": user["email"],
        "role": user["role"],
    }
    return jsonify(user=session["user"])


@app.post("/api/admin/login")
def admin_login():
    data = request_data()
    identifier = str(data.get("identifier", "")).strip()
    password = str(data.get("password", ""))
    user = query_one(
        """SELECT id, name, student_id, email, password_hash, role
           FROM users WHERE (student_id = %s OR email = %s) AND role = 'admin'""",
        (identifier, identifier.lower()),
    )
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Warden ID/email or password is incorrect."), 401

    session.clear()
    session["user"] = {
        "id": user["id"], "name": user["name"], "student_id": user["student_id"],
        "email": user["email"], "role": user["role"],
    }
    return jsonify(user=session["user"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(message="You have been logged out.")


@app.get("/api/dashboard")
@login_required(role="student")
def student_dashboard():
    user_id = session["user"]["id"]
    profile = query_one(
        "SELECT name, student_id, email, hostel_block, room_number FROM users WHERE id = %s",
        (user_id,),
    )
    counts = query_one(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(status = 'Pending'), 0) AS pending,
                  COALESCE(SUM(status = 'In Progress'), 0) AS in_progress,
                  COALESCE(SUM(status = 'Resolved'), 0) AS resolved
           FROM complaints WHERE user_id = %s""",
        (user_id,),
    )
    return jsonify(profile=profile, counts=counts)


@app.get("/api/complaints")
@login_required(role="student")
def my_complaints():
    complaints = query_all(
        """SELECT c.id, c.complaint_id, c.category, c.title, c.description,
                  c.hostel_block, c.room_number, c.status, c.resolution_remarks,
                  DATE_FORMAT(c.created_at, '%Y-%m-%d %H:%i') AS created_at,
                  f.rating AS feedback_rating, f.comment AS feedback_comment
           FROM complaints c LEFT JOIN feedback f
             ON f.complaint_id = c.id AND f.user_id = c.user_id
           WHERE c.user_id = %s ORDER BY c.created_at DESC, c.id DESC""",
        (session["user"]["id"],),
    )
    return jsonify(complaints=complaints)


@app.get("/api/complaints/<int:complaint_id>")
@login_required(role="student")
def complaint_detail(complaint_id):
    complaint = query_one(
        """SELECT c.id, c.complaint_id, c.category, c.title, c.description,
                  c.hostel_block, c.room_number, c.status, c.resolution_remarks,
                  DATE_FORMAT(c.created_at, '%Y-%m-%d %H:%i') AS created_at,
                  f.rating AS feedback_rating, f.comment AS feedback_comment
           FROM complaints c LEFT JOIN feedback f
             ON f.complaint_id = c.id AND f.user_id = c.user_id
           WHERE c.id = %s AND c.user_id = %s""",
        (complaint_id, session["user"]["id"]),
    )
    if not complaint:
        return jsonify(error="Complaint not found."), 404
    return jsonify(complaint=complaint)


@app.post("/api/complaints")
@login_required(role="student")
def create_complaint():
    data = request_data()
    fields = ("category", "title", "description", "hostel_block", "room_number")
    values = {field: str(data.get(field, "")).strip() for field in fields}
    if any(not value for value in values.values()):
        return jsonify(error="Please complete every field."), 400
    categories = {
        "Electrical", "Plumbing", "Cleaning", "Food", "Water", "Wi-Fi",
        "Room Maintenance", "Other",
    }
    if values["category"] not in categories:
        return jsonify(error="Choose a valid complaint category."), 400

    complaint_id = execute_insert(
        """INSERT INTO complaints
           (complaint_id, user_id, category, title, description, hostel_block, room_number)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (uuid4().hex, session["user"]["id"], *(values[field] for field in fields)),
    )
    public_id = f"HC-{datetime.now().strftime('%Y%m%d')}-{complaint_id:06d}"
    execute_update("UPDATE complaints SET complaint_id = %s WHERE id = %s", (public_id, complaint_id))
    return jsonify(message="Your complaint has been submitted.", complaint_id=public_id), 201


@app.post("/api/complaints/<int:complaint_id>/feedback")
@login_required(role="student")
def create_feedback(complaint_id):
    data = request_data()
    try:
        rating = int(data.get("rating", 0))
    except (TypeError, ValueError):
        rating = 0
    comment = str(data.get("comment", "")).strip()
    if rating not in range(1, 6) or not comment:
        return jsonify(error="Choose a rating from 1 to 5 and enter your feedback."), 400

    complaint = query_one(
        """SELECT id FROM complaints
           WHERE id = %s AND user_id = %s AND status = 'Resolved'""",
        (complaint_id, session["user"]["id"]),
    )
    if not complaint:
        return jsonify(error="Feedback is available only for your resolved complaints."), 400
    try:
        feedback_id = execute_insert(
            "INSERT INTO feedback (complaint_id, user_id, rating, comment) VALUES (%s, %s, %s, %s)",
            (complaint_id, session["user"]["id"], rating, comment),
        )
    except IntegrityError:
        return jsonify(error="Feedback has already been submitted for this complaint."), 409
    return jsonify(message="Thank you for your feedback.", feedback_id=feedback_id), 201


@app.get("/api/admin/complaints")
@login_required(role="admin")
def all_complaints():
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    search = request.args.get("q", "").strip()
    categories = {
        "Electrical", "Plumbing", "Cleaning", "Food", "Water", "Wi-Fi",
        "Room Maintenance", "Other",
    }
    statuses = {"Pending", "In Progress", "Resolved", "Rejected"}
    if category and category not in categories:
        return jsonify(error="Choose a valid complaint category."), 400
    if status and status not in statuses:
        return jsonify(error="Choose a valid complaint status."), 400

    conditions = []
    values = []
    if category:
        conditions.append("c.category = %s")
        values.append(category)
    if status:
        conditions.append("c.status = %s")
        values.append(status)
    if search:
        conditions.append("(c.complaint_id LIKE %s OR c.title LIKE %s OR u.name LIKE %s OR u.student_id LIKE %s)")
        values.extend([f"%{search}%"] * 4)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    complaints = query_all(
        """SELECT c.id, c.category, c.title, c.description, c.room_number,
                  c.complaint_id, c.hostel_block, c.status, c.resolution_remarks,
                  DATE_FORMAT(c.created_at, '%Y-%m-%d %H:%i') AS created_at,
                  u.name AS student_name, u.student_id, u.email AS student_email
           FROM complaints c JOIN users u ON u.id = c.user_id """
        + where_clause + " ORDER BY c.created_at DESC, c.id DESC",
        tuple(values),
    )
    return jsonify(complaints=complaints)


@app.get("/api/admin/dashboard")
@login_required(role="admin")
def admin_dashboard():
    counts = query_one(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(status = 'Pending'), 0) AS pending,
                  COALESCE(SUM(status = 'In Progress'), 0) AS in_progress,
                  COALESCE(SUM(status = 'Resolved'), 0) AS resolved
           FROM complaints"""
    )
    return jsonify(counts=counts)


@app.put("/api/admin/complaints/<int:complaint_id>/status")
@login_required(role="admin")
def update_complaint_status(complaint_id):
    status = str(request_data().get("status", "")).strip()
    remarks = str(request_data().get("resolution_remarks", "")).strip()
    if status not in {"Pending", "In Progress", "Resolved", "Rejected"}:
        return jsonify(error="Choose a valid complaint status."), 400

    changed = execute_update(
        "UPDATE complaints SET status = %s, resolution_remarks = %s WHERE id = %s",
        (status, remarks, complaint_id),
    )
    if changed == 0 and not query_one("SELECT id FROM complaints WHERE id = %s", (complaint_id,)):
        return jsonify(error="Complaint not found."), 404
    return jsonify(message="Complaint status updated.")


if __name__ == "__main__":
    try:
        initialize_database()
        print(f"Connected to MySQL database: {DATABASE_NAME}")
    except mysql.connector.Error as error:
        print(f"MySQL unavailable; the website will start without database access: {error}")
    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
