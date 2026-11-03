import json
import os
import uuid

import boto3
import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
S3_BUCKET = os.environ["S3_BUCKET"]
DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]
MAX_FILE_SIZE = 200 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE + (10 * 1024 * 1024)
ALLOWED_EXTENSIONS = {"pdf", "zip"}

s3 = boto3.client("s3", region_name=AWS_REGION)


def get_db_credentials():
    """Read DB credentials from a file mounted by Secrets Store CSI Driver.

    The default mounted file is /mnt/secrets/db-secret and must contain JSON
    with username/password (or DB_USER/DB_PASSWORD) keys. No Secrets Manager
    API call is made by this backend.
    """
    secret_file = os.environ.get("DB_SECRET_FILE", "/mnt/secrets/db-secret")
    with open(secret_file, "r", encoding="utf-8") as mounted_secret:
        secret = json.load(mounted_secret)
    username = secret.get("username") or secret.get("DB_USER")
    password = secret.get("password") or secret.get("DB_PASSWORD")
    if not username or not password:
        raise RuntimeError("Mounted secret JSON must contain username and password fields")
    return username, password


def get_db_connection():
    username, password = get_db_credentials()
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=username,
        password=password,
        connect_timeout=5,
    )


def init_db():
    """Create the shared files table safely when multiple pods start together.

    The transaction-level advisory lock serializes schema initialization across
    replicas. Every backend variant uses the same lock ID and database schema.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Must be acquired before CREATE TABLE. The lock is released on commit
            # or rollback, including when initialization raises an exception.
            cursor.execute("SELECT pg_advisory_xact_lock(741852963)")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    upload_id VARCHAR(100) NOT NULL,
                    folder_name VARCHAR(255),
                    file_name VARCHAR(255) NOT NULL,
                    s3_key TEXT NOT NULL UNIQUE,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.get("/")
def home():
    return jsonify({"message": "File application is running"})


@app.get("/health/startup")
def health_startup():
    return jsonify({"status": "started"}), 200


@app.get("/health/live")
def health_live():
    # Liveness checks only the Flask process; an RDS outage should not restart every pod.
    return jsonify({"status": "alive"}), 200


@app.get("/health/ready")
def health_ready():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        return jsonify({"status": "ready"}), 200
    except Exception:
        app.logger.exception("Readiness check failed")
        return jsonify({"status": "not_ready"}), 503
    finally:
        if conn:
            conn.close()


@app.get("/api/db-test")
def db_test():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
        return jsonify({"message": "Database connection successful", "database_version": version})
    except Exception:
        app.logger.exception("Database test failed")
        return jsonify({"message": "Database connection failed"}), 500
    finally:
        if conn:
            conn.close()


@app.post("/api/upload")
@app.post("/upload")  # Backward-compatible alias

def upload_files():
    uploaded_files = request.files.getlist("file")
    if not uploaded_files:
        return jsonify({"error": "No file provided"}), 400

    folder_name = request.form.get("folderName", "").strip()
    safe_folder = secure_filename(folder_name) if folder_name else ""
    conn = None
    uploaded_s3_keys = []
    try:
        conn = get_db_connection()
        upload_id = str(uuid.uuid4())
        results = []
        with conn.cursor() as cursor:
            for uploaded in uploaded_files:
                if not uploaded or not uploaded.filename:
                    continue
                filename = secure_filename(uploaded.filename)
                if not filename:
                    raise ValueError("Invalid filename")
                if not allowed_file(filename):
                    raise ValueError(f"Only PDF and ZIP files are allowed: {filename}")
                data = uploaded.read(MAX_FILE_SIZE + 1)
                if len(data) > MAX_FILE_SIZE:
                    raise ValueError(f"File exceeds the 200 MB limit: {filename}")

                file_id = str(uuid.uuid4())
                prefix = f"uploads/{safe_folder}/" if safe_folder else "uploads/"
                s3_key = f"{prefix}{file_id}-{filename}"
                s3.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=data)
                uploaded_s3_keys.append(s3_key)

                cursor.execute("""
                    INSERT INTO files (upload_id, folder_name, file_name, s3_key)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, uploaded_at
                """, (upload_id, folder_name, filename, s3_key))
                row = cursor.fetchone()
                results.append({
                    "id": row[0], "upload_id": upload_id,
                    "folder_name": folder_name, "file_name": filename,
                    "s3_key": s3_key,
                    "uploaded_at": row[1].isoformat() if row[1] else None,
                })

        if not results:
            conn.rollback()
            return jsonify({"error": "No valid files were provided"}), 400
        conn.commit()
        return jsonify({"message": "File(s) uploaded successfully", "files": results}), 200
    except ValueError as exc:
        if conn:
            conn.rollback()
        for key in uploaded_s3_keys:
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=key)
            except Exception:
                app.logger.exception("Failed to roll back S3 upload")
        return jsonify({"error": str(exc)}), 400
    except Exception:
        if conn:
            conn.rollback()
        for key in uploaded_s3_keys:
            try:
                s3.delete_object(Bucket=S3_BUCKET, Key=key)
            except Exception:
                app.logger.exception("Failed to roll back S3 upload")
        app.logger.exception("File upload failed")
        return jsonify({"error": "File upload failed"}), 500
    finally:
        if conn:
            conn.close()


@app.get("/api/files")
@app.get("/files")  # Backward-compatible alias

def list_files():
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, upload_id, folder_name, file_name, s3_key, uploaded_at
                FROM files ORDER BY uploaded_at DESC
            """)
            rows = cursor.fetchall()
        return jsonify({"files": [
            {"id": r[0], "upload_id": r[1], "folder_name": r[2],
             "file_name": r[3], "s3_key": r[4],
             "uploaded_at": r[5].isoformat() if r[5] else None}
            for r in rows
        ]})
    except Exception:
        app.logger.exception("Failed to list files")
        return jsonify({"error": "Failed to load files"}), 500
    finally:
        if conn:
            conn.close()


@app.get("/api/download/<path:s3_key>")
@app.get("/download/<path:s3_key>")  # Express proxy strips the /api mount prefix
def download_file(s3_key):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT file_name FROM files WHERE s3_key = %s", (s3_key,))
            row = cursor.fetchone()
        if not row:
            return jsonify({"error": "File not found"}), 404
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": s3_key},
            ExpiresIn=172800,
        )
        return jsonify({"download_url": url, "file_name": row[0]})
    except Exception:
        app.logger.exception("Failed to generate download URL")
        return jsonify({"error": "Failed to generate download URL"}), 500
    finally:
        if conn:
            conn.close()


@app.delete("/api/delete/<path:s3_key>")
@app.delete("/delete/<path:s3_key>")  # Express proxy strips the /api mount prefix
def delete_file(s3_key):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM files WHERE s3_key = %s", (s3_key,))
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "File not found"}), 404
            # Delete the object first. Keep the DB row if S3 deletion fails.
            s3.delete_object(Bucket=S3_BUCKET, Key=s3_key)
            cursor.execute("DELETE FROM files WHERE id = %s", (row[0],))
        conn.commit()
        return jsonify({"message": "File deleted successfully"}), 200
    except Exception:
        if conn:
            conn.rollback()
        app.logger.exception("Failed to delete file")
        return jsonify({"error": "File deletion failed"}), 500
    finally:
        if conn:
            conn.close()


@app.errorhandler(413)
def file_too_large(_error):
    return jsonify({"error": "Request exceeds the 200 MB file limit"}), 413


if __name__ == "__main__":
    # Fail fast if RDS or the selected credential source is unavailable.
    init_db()
    app.run(host="0.0.0.0", port=5000)
