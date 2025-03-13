import streamlit as st
import sqlite3
import requests
from requests_oauthlib import OAuth2Session
from io import BytesIO
from reportlab.pdfgen import canvas

# Load Secrets from streamlit secrets.toml
CLIENT_ID = st.secrets["oauth"]["client_id"]
CLIENT_SECRET = st.secrets["oauth"]["client_secret"]
REDIRECT_URI = st.secrets["oauth"]["redirect_uri"]

# OAuth URLs
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

DB_FILE = "users.db"

# Connect to database
def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# Ensure users and admins tables exist
def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            role TEXT,
            leave_balance INTEGER DEFAULT 10
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'Pending',
            email TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()

# Assign role based on email
def assign_role(email):
    if email.startswith("220") and email.endswith("@kiit.ac.in"):
        return "Student"
    return "Faculty"

# Save user to database
def save_user(name, email):
    conn = get_db_connection()
    cursor = conn.cursor()
    role = assign_role(email)
    
    cursor.execute(
        "INSERT OR IGNORE INTO users (name, email, role, leave_balance) VALUES (?, ?, ?, ?)",
        (name, email, role, 20 if role == "Student" else 30)
    )
    conn.commit()
    conn.close()

# Admin Authentication
def authenticate_admin(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM admins WHERE username = ? AND password = ?", (username, password))
    admin = cursor.fetchone()
    
    conn.close()
    return admin is not None

# Admin login screen
def admin_login():
    st.subheader("🔐 Admin Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if authenticate_admin(username, password):
            st.session_state["role"] = "Admin"
            st.session_state["admin_user"] = username
            st.success("✅ Logged in as Admin")
            st.experimental_rerun()
        else:
            st.error("❌ Invalid credentials")

# Function to get user info (role & leave balance)
def get_user_info(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, leave_balance FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user if user else ("Unknown", 0)

# Google OAuth login for students & faculty
def google_login():
    st.title("🎓 Google Sign-In, Certificate & Leave System")

    if "token" not in st.session_state:
        google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=["openid", "email", "profile"])
        authorization_url, state = google.authorization_url(AUTHORIZATION_BASE_URL, access_type="offline")
        st.session_state["oauth_state"] = state
        st.markdown(f"[🔑 Login with Google]({authorization_url})", unsafe_allow_html=True)

    if "code" in st.query_params:
        code = st.query_params["code"]
        google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, state=st.session_state["oauth_state"])
        
        try:
            token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, code=code)
            st.session_state["token"] = token
            user_info = requests.get(USER_INFO_URL, headers={"Authorization": f"Bearer {token['access_token']}"}).json()
            st.session_state["user"] = user_info
            st.experimental_rerun()
        except Exception as e:
            st.error(f"OAuth Error: {e}")

# Leave application functionality
def apply_for_leave(user_email, user_name, role):
    st.subheader("🏖 Apply for Leave")
    leave_type = st.selectbox("Leave Type", ["Sick Leave", "Casual Leave", "Vacation"])
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")
    reason = st.text_area("Reason for Leave")

    leave_days = (end_date - start_date).days + 1

    if st.button("Submit Leave Request"):
        if leave_days <= 0:
            st.error("❌ Invalid leave dates.")
        else:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, leave_balance FROM users WHERE email = ?", (user_email,))
            user = cursor.fetchone()

            if user:
                user_id, available_leaves = user
                if available_leaves < leave_days:
                    st.error(f"❌ Not enough leaves! Only {available_leaves} left.")
                else:
                    cursor.execute("UPDATE users SET leave_balance = ? WHERE email = ?", (available_leaves - leave_days, user_email))
                    cursor.execute(
                        "INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, reason, email) VALUES (?, ?, ?, ?, ?, ?)",
                        (user_id, leave_type, start_date, end_date, reason, user_email)
                    )
                    conn.commit()
                    st.success(f"✅ Leave request submitted! {available_leaves - leave_days} leaves remaining.")
            conn.close()

# Main App Flow
initialize_db()

if "role" not in st.session_state:
    st.title("Select Your Role")
    role_choice = st.radio("Are you a:", ["Student", "Faculty", "Admin"])

    if st.button("Continue"):
        if role_choice == "Admin":
            st.session_state["role"] = "Admin"
        else:
            st.session_state["role"] = role_choice
        st.experimental_rerun()

elif st.session_state["role"] == "Admin":
    admin_login()

elif "user" not in st.session_state:
    google_login()

else:
    user = st.session_state["user"]
    user_email = user["email"]
    user_name = user["name"]
    
    save_user(user_name, user_email)
    role, leave_balance = get_user_info(user_email)

    st.write(f"👤 **Name:** {user_name} | **Role:** {role} | 🏖️ **Remaining Leave Balance:** {leave_balance} days")

    if st.button("Generate Certificate"):
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer)
        c.drawString(200, 700, "Certificate of Achievement")
        c.drawString(220, 650, f"Awarded to: {user_name}")
        c.save()
        
        st.download_button(label="📄 Download Certificate", data=pdf_buffer.getvalue(), file_name="certificate.pdf", mime="application/pdf")

    apply_for_leave(user_email, user_name, role)
