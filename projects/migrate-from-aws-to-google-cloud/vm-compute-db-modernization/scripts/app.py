# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Flask Application Demo.
Provides API endpoints to manage users in a PostgreSQL database.
"""

import os
import socket
import time

import psycopg2
from flask import Flask, jsonify, request
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "port": int(os.environ.get("DB_PORT", 5432)),
    "database": os.environ.get("DB_NAME", "appdb"),
    "user": os.environ.get("DB_USER", "appuser"),
    "password": os.environ.get("DB_PASSWORD", ""),
}


def get_db():
    """Establish a connection to the PostgreSQL database with retries."""
    conn = None
    while conn is None:
        try:
            conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        except psycopg2.OperationalError:
            print("Database not ready, waiting...")
            time.sleep(1)
    return conn


@app.route("/health")
def health():
    """Health check endpoint to verify database connectivity."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify(
            {
                "status": "healthy",
                "database": "connected",
                "hostname": socket.gethostname(),
                "db_host": DB_CONFIG["host"],
            }
        )
    except psycopg2.Error as e:
        return (
            jsonify(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "hostname": socket.gethostname(),
                }
            ),
            500,
        )


@app.route("/")
def index():
    """Root endpoint listing available API routes."""
    return jsonify(
        {
            "message": "Application API",
            "version": "1.0.0",
            "hostname": socket.gethostname(),
            "endpoints": [
                {
                    "method": "GET",
                    "path": "/health",
                    "description": "Health check",
                },
                {
                    "method": "GET",
                    "path": "/api/users",
                    "description": "List all users",
                },
                {
                    "method": "GET",
                    "path": "/api/users/<id>",
                    "description": "Get user by ID",
                },
                {
                    "method": "POST",
                    "path": "/api/users",
                    "description": "Create new user",
                },
                {
                    "method": "DELETE",
                    "path": "/api/users/<id>",
                    "description": "Delete user",
                },
            ],
        }
    )


@app.route("/api/users", methods=["GET"])
def get_users():
    """Fetch all users from the database."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users ORDER BY id")
        users = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify({"count": len(users), "users": users})
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Fetch a single user by ID."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user:
            return jsonify(user)
        return jsonify({"error": "User not found"}), 404
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users", methods=["POST"])
def create_user():
    """Create a new user in the database."""
    try:
        data = request.get_json()
        if not data or "name" not in data or "email" not in data:
            return jsonify({"error": "name and email are required"}), 400
        conn = get_db()
        cur = conn.cursor()
        query = (
            "INSERT INTO users (name, email, department) "
            "VALUES (%s, %s, %s) RETURNING *"
        )
        cur.execute(
            query,
            (data["name"], data["email"], data.get("department", "General")),
        )
        user = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(user), 201
    except psycopg2.IntegrityError:
        return jsonify({"error": "Email already exists"}), 409
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    """Delete a user by ID."""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if deleted:
            return jsonify({"message": f"User {user_id} deleted"})
        return jsonify({"error": "User not found"}), 404
    except psycopg2.Error as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
