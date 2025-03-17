from flask import Flask, request, jsonify, send_file
import sqlite3
import os
import datetime
import pandas as pd
import json
import time
import PyPDF2
from dotenv import load_dotenv
from groq import Groq
from reportlab.pdfgen import canvas

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Flask App & Groq Client
app = Flask(__name__)
client = Groq(api_key=GROQ_API_KEY)

# ✅ Database Connection
def get_db_connection():
    conn = sqlite3.connect("leave_management.db", timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

# ✅ Create Tables If Not Exists
def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            mentor_id TEXT,
            days INTEGER,
            start_date TEXT DEFAULT CURRENT_DATE,
            end_date TEXT,
            status TEXT CHECK(status IN ('pending', 'approved', 'rejected'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mentor_assignments (
            student_id TEXT PRIMARY KEY,
            mentor_id TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS academic_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT
        )
    """)

    conn.commit()
    conn.close()

initialize_db()

# ✅ Assign Mentor API
@app.route("/assign-mentor", methods=["POST"])
def assign_mentor():
    data = request.json
    student_id = data["student_id"]
    mentor_id = data["mentor_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO mentor_assignments (student_id, mentor_id) VALUES (?, ?)", (student_id, mentor_id))
    conn.commit()
    conn.close()

    return jsonify({"message": f"✅ Assigned Mentor {mentor_id} to Student {student_id}."})

# ✅ Request Leave API (Auto-approve if ≤ 5 days)
@app.route("/leave", methods=["POST"])
def process_leave():
    data = request.json
    student_id = data["student_id"]
    days = data["days"]
    start_date = datetime.date.today().strftime("%Y-%m-%d")
    end_date = (datetime.date.today() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mentor_id FROM mentor_assignments WHERE student_id = ?", (student_id,))
    mentor = cursor.fetchone()

    if days <= 5:
        status = "approved"
        mentor_id = "Auto-Approved"
    elif mentor:
        status = "pending"
        mentor_id = mentor["mentor_id"]
    else:
        conn.close()
        return jsonify({"message": "❌ No mentor found for this student."}), 400

    cursor.execute("""
        INSERT INTO leave_requests (student_id, mentor_id, days, start_date, end_date, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id, mentor_id, days, start_date, end_date, status))

    conn.commit()
    conn.close()

    return jsonify({"message": f"✅ Leave request for {days} days sent to {mentor_id}. Status: {status}."})

# ✅ Fetch Student Leave Requests
@app.route("/student-leave-status", methods=["GET"])
def student_leave_status():
    student_id = request.args.get("student_id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT mentor_id, days, start_date, end_date, status FROM leave_requests WHERE student_id = ?", (student_id,))
    requests = cursor.fetchall()
    conn.close()

    return jsonify({"requests": [dict(req) for req in requests]})

# ✅ Fetch Mentor Leave Requests
@app.route("/mentor-leave-requests", methods=["GET"])
def mentor_leave_requests():
    mentor_id = request.args.get("mentor_id")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, student_id, days, start_date, end_date, status FROM leave_requests WHERE mentor_id = ? AND status = 'pending'", (mentor_id,))
    requests = cursor.fetchall()
    conn.close()

    return jsonify({"requests": [dict(req) for req in requests]})

# ✅ Approve Leave (Mentor Action)
@app.route("/approve-leave", methods=["POST"])
def approve_leave():
    data = request.json
    leave_id = data["leave_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE leave_requests SET status = 'approved' WHERE id = ?", (leave_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "✅ Leave request approved."})

# ✅ Reject Leave (Mentor Action)
@app.route("/reject-leave", methods=["POST"])
def reject_leave():
    data = request.json
    leave_id = data["leave_id"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE leave_requests SET status = 'rejected' WHERE id = ?", (leave_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "❌ Leave request rejected."})

# ✅ Upload AI Training Data (Admin)
@app.route("/upload-data", methods=["POST"])
def upload_ai_data():
    if "file" not in request.files:
        return jsonify({"message": "❌ No file uploaded."}), 400

    file = request.files["file"]
    filename = file.filename

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if filename.endswith(".csv") or filename.endswith(".xlsx"):
            df = pd.read_csv(file) if filename.endswith(".csv") else pd.read_excel(file)
            for _, row in df.iterrows():
                cursor.execute("INSERT INTO academic_docs (content) VALUES (?)", (json.dumps(row.to_dict()),))
            conn.commit()

        elif filename.endswith(".json"):
            data = json.load(file)
            cursor.execute("INSERT INTO academic_docs (content) VALUES (?)", (json.dumps(data),))
            conn.commit()

        elif filename.endswith(".pdf"):
            reader = PyPDF2.PdfReader(file)
            text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            cursor.execute("INSERT INTO academic_docs (content) VALUES (?)", (text,))
            conn.commit()
        else:
            return jsonify({"message": "❌ Invalid file format. Supported formats: CSV, XLSX, JSON, PDF"}), 400

        conn.close()
        return jsonify({"message": "✅ AI Training Data Uploaded Successfully."})

    except Exception as e:
        return jsonify({"message": f"❌ Error processing file: {str(e)}"}), 500

# ✅ AI Academic Query Processing (Groq SDK)
@app.route("/academic", methods=["POST"])
def academic_query():
    data = request.json
    query = data["query"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM academic_docs")
    documents = cursor.fetchall()
    conn.close()

    knowledge_base = " ".join([doc["content"] for doc in documents])[:4000]

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": "You are an academic assistant."}, {"role": "user", "content": f"{query}\n\nContext:\n{knowledge_base}"}],
            model="llama-3.3-70b-versatile",
        )
        return jsonify({"response": chat_completion.choices[0].message.content})

    except Exception as e:
        return jsonify({"response": f"❌ AI Error: {str(e)}"})

# ✅ Run Server
if __name__ == "__main__":
    app.run(debug=True)
