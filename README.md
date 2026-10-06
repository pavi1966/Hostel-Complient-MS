# Hostel Complaint Management System

A student and warden complaint portal built with HTML, CSS, JavaScript, Flask, and MySQL. Flask serves the website and JSON API from the same origin. Account passwords are hashed; registrations, complaints, status changes, and feedback are stored in MySQL.

## Requirements

- Python 3.10 or newer
- MySQL Community Server 8.0+ running as a Windows service
- A MySQL account permitted to create a database and tables
- Google Chrome (optional; the website also opens in the VS Code browser)

If MySQL is not installed, install MySQL Community Server from https://dev.mysql.com/downloads/installer/. In MySQL Installer, install **MySQL Server**, configure it as a Windows service, set a root password, and start the service. The application cannot save or retrieve accounts or complaints until MySQL is running.

## Install and start (Windows PowerShell)

Run these commands from the project root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r BACKEND\requirements.txt
$env:MYSQL_HOST = "localhost"
$env:MYSQL_PORT = "3306"
$env:MYSQL_USER = "root"
$env:MYSQL_PASSWORD = "your-mysql-root-password"
$env:MYSQL_DATABASE = "hostel_complaint_db"
$env:FLASK_SECRET_KEY = "replace-this-with-a-long-random-value"
python BACKEND\app.py
```

On first startup Flask creates `hostel_complaint_db` and applies `schema.sql`. The configured MySQL user needs database/table creation permissions. Open http://127.0.0.1:5000. If MySQL is unavailable, Flask still serves the home page and `/api/health` reports `database: unavailable`; database-backed actions return HTTP 503 rather than using sample data.

If MySQL root has no password, set `$env:MYSQL_PASSWORD = ""`. Keep MySQL credentials in the backend environment only; they are never sent to the browser.

## Create the warden account

In a second PowerShell terminal, set the same `MYSQL_*` variables, then run:

```powershell
$env:ADMIN_NAME = "Hostel Warden"
$env:ADMIN_STUDENT_ID = "WARDEN001"
$env:ADMIN_EMAIL = "warden@example.com"
$env:ADMIN_PASSWORD = "choose-a-password-at-least-8-characters"
python BACKEND\seed_admin.py
```

The admin seed command stores a hashed password. Warden accounts sign in from the **Warden** button on the home page; student accounts cannot access the admin APIs.

## Student workflow

Students register using a unique student ID and email, sign in using either identifier, submit complaints, and view status and resolution remarks. Complaints receive IDs such as `HC-20261003-000001` and begin as `Pending`. Wardens can set `Pending`, `In Progress`, `Resolved`, or `Rejected`. Students may submit one rating and comment after a complaint is resolved.

## Tests

With the virtual environment active:

```powershell
python -m unittest discover -s BACKEND -p "test_*.py" -v
```

The API tests mock database calls, so a local MySQL service is not required to run the test suite.

## Main API

- `POST /api/register`, `POST /api/login`, `POST /api/admin/login`, `POST /api/logout`
- `GET /api/session`, `GET /api/health`
- `POST /api/complaints`, `GET /api/complaints`, `GET /api/complaints/<id>`
- `GET /api/dashboard`, `POST /api/complaints/<id>/feedback`
- `GET /api/admin/complaints?q=&category=&status=`
- `GET /api/admin/dashboard`, `PUT /api/admin/complaints/<id>/status`
