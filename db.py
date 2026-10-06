import os
from pathlib import Path
import re

import mysql.connector


ROOT_DIR = Path(__file__).resolve().parent.parent
SCHEMA_FILE = ROOT_DIR / "schema.sql"
DATABASE_NAME = os.getenv("MYSQL_DATABASE", "hostel_complaint_db")

if not re.fullmatch(r"[A-Za-z0-9_]+", DATABASE_NAME):
    raise ValueError("MYSQL_DATABASE may contain only letters, numbers, and underscores")


def connect_to_mysql(include_database=True):
    options = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "root"),
        "password": os.getenv("MYSQL_PASSWORD", "renuka@123"),
    }
    if include_database:
        options["database"] = DATABASE_NAME
    return mysql.connector.connect(**options)


def initialize_database():
    server = connect_to_mysql(include_database=False)
    cursor = server.cursor()
    try:
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DATABASE_NAME}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
    finally:
        cursor.close()
        server.close()

    connection = connect_to_mysql()
    cursor = connection.cursor()
    try:
        for statement in SCHEMA_FILE.read_text(encoding="utf-8").split(";"):
            if statement.strip():
                cursor.execute(statement)
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def query_one(sql, values=()):
    connection = connect_to_mysql()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, values)
        return cursor.fetchone()
    finally:
        cursor.close()
        connection.close()


def query_all(sql, values=()):
    connection = connect_to_mysql()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, values)
        return cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def execute_insert(sql, values=()):
    connection = connect_to_mysql()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, values)
        connection.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        connection.close()


def execute_update(sql, values=()):
    connection = connect_to_mysql()
    cursor = connection.cursor()
    try:
        cursor.execute(sql, values)
        connection.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        connection.close()

