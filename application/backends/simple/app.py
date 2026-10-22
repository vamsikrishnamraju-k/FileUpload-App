import os
import uuid

import boto3
import psycopg2
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

S3_BUCKET = os.environ["S3_BUCKET"]

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ["DB_NAME"]

MAX_FILE_SIZE = 200 * 1024 * 1024  # 200 MB
ALLOWED_EXTENSIONS = {"pdf", "zip"}

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION
)


def get_db_credentials():
    username = os.environ["DB_USER"]
    password = os.environ["DB_PASSWORD"]
    return username, password


def get_db_connection():
    username, password = get_db_credentials()

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=username,
        password=password,
        connect_timeout=5
    )


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Matches the existing project database schema.
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
    cursor.close()
    conn.close()


def allowed_file(filename):
    if "." not in filename:
        return False

    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "File application is running"
    })


@app.route("/api/db-test", methods=["GET"])
def db_test():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT version();")
        result = cursor.fetchone()

        return jsonify({
            "message": "Database connection successful",
            "database_version": result[0]
        })

    except Exception as e:
        return jsonify({
            "message": "Database connection failed",
            "error": str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


@app.route("/upload", methods=["POST"])
def upload_file():
    uploaded_files = request.files.getlist("file")

    if not uploaded_files:
        return jsonify({
            "error": "No file provided"
        }), 400

    folder_name = request.form.get("folderName", "").strip()

    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        upload_id = str(uuid.uuid4())
        uploaded_results = []

        for uploaded in uploaded_files:

            if uploaded.filename == "":
                continue

            original_filename = secure_filename(uploaded.filename)

            if not original_filename:
                return jsonify({
                    "error": "Invalid filename"
                }), 400

            if not allowed_file(original_filename):
                return jsonify({
                    "error": f"Only PDF and ZIP files are allowed: {original_filename}"
                }), 400

            data = uploaded.read(MAX_FILE_SIZE + 1)

            if len(data) > MAX_FILE_SIZE:
                return jsonify({
                    "error": f"File exceeds the 200 MB limit: {original_filename}"
                }), 400

            file_id = str(uuid.uuid4())

            if folder_name:
                safe_folder = secure_filename(folder_name)
                if safe_folder:
                    s3_key = (
                        f"uploads/{safe_folder}/"
                        f"{file_id}-{original_filename}"
                    )
                else:
                    s3_key = f"uploads/{file_id}-{original_filename}"
            else:
                s3_key = f"uploads/{file_id}-{original_filename}"

            # Upload to the private S3 bucket.
            s3.put_object(
                Bucket=S3_BUCKET,
                Key=s3_key,
                Body=data
            )

            # Store metadata using the existing DB schema.
            cursor.execute(
                """
                INSERT INTO files
                (upload_id, folder_name, file_name, s3_key)
                VALUES (%s, %s, %s, %s)
                RETURNING id, uploaded_at
                """,
                (
                    upload_id,
                    folder_name,
                    original_filename,
                    s3_key
                )
            )

            row = cursor.fetchone()

            uploaded_results.append({
                "id": row[0],
                "upload_id": upload_id,
                "folder_name": folder_name,
                "file_name": original_filename,
                "s3_key": s3_key,
                "uploaded_at": row[1].isoformat() if row[1] else None
            })

        if not uploaded_results:
            return jsonify({
                "error": "No valid files were provided"
            }), 400

        conn.commit()

        return jsonify({
            "message": "File(s) uploaded successfully",
            "files": uploaded_results
        }), 200

    except Exception as e:

        if conn:
            conn.rollback()

        import traceback
        traceback.print_exc()

        return jsonify({
            "error": "File upload failed",
            "details": str(e)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# Frontend currently calls /files, so keep this endpoint compatible.
@app.route("/files", methods=["GET"])
def list_files():
    conn = None
    cursor = None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, upload_id, folder_name, file_name, s3_key, uploaded_at
            FROM files
            ORDER BY uploaded_at DESC
        """)

        rows = cursor.fetchall()

        files = []

        for row in rows:
            files.append({
                "id": row[0],
                "upload_id": row[1],
                "folder_name": row[2],
                "file_name": row[3],
                "s3_key": row[4],
                "uploaded_at": row[5].isoformat() if row[5] else None
            })

        return jsonify({
            "files": files
        })

    except Exception as e:

        return jsonify({
            "error": "Failed to load files",
            "details": str(e)
        }), 500

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# Also support the /api/files form if needed.
@app.route("/api/files", methods=["GET"])
def api_list_files():
    return list_files()


if __name__ == "__main__":
    init_db()

    app.run(
        host="0.0.0.0",
        port=5000
    )
