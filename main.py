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
TOKEN_URL = "https://accounts.google.com/o/oauth2/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

DB_FILE = "users.db"

# Connect to database
def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

# Ensure users table exists
def initialize_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            role TEXT,
            password TEXT,
            leave_balance INTEGER DEFAULT 10,
            total_leaves INTEGER DEFAULT 0
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

# Generate Certificate
def generate_certificate(name, role, cert_type):
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(200, 700, f"{role} Certificate")
    c.setFont("Helvetica", 18)
    c.drawString(220, 650, f"Awarded to: {name}")
    c.setFont("Helvetica", 15)
    c.drawString(220, 600, f"Type: {role}")
    c.drawString(220, 550, f"Date: {st.date_input('Date')}")
    c.drawString(220, 500, f"Certified By: KIIT University")
    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer

# Login
def assign_role(email):
    if email.startswith("220") and email.endswith("@kiit.ac.in"):
        return "Student"
    return "Teacher"

def save_user(email, role):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT OR IGNORE INTO users (name, email, role, leave_balance) VALUES (?, ?, ?, ?)",
        (email, email, role, 20 if role == "Student" else 30)
    )
    
    conn.commit()
    conn.close()

def get_user_info(email):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, leave_balance FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    return user if user else ("Unknown", 0)

def admin_login(username, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ? AND password = ? AND role = 'Admin'", (username, password))
    user = cursor.fetchone()
    conn.close()
    
    return user is not None

st.title("🎓 Google Sign-In, Certificate & Leave System")
role_selection = st.radio("Select your role:", ["Student / Teacher", "Admin"])

if role_selection == "Student / Teacher":
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
        except Exception as e:
            st.error(f"OAuth Error: {e}")

elif role_selection == "Admin":
    st.subheader("🔐 Admin Login")
    admin_username = st.text_input("Username")
    admin_password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if admin_login(admin_username, admin_password):
            st.success("✅ Admin login successful!")
            st.session_state["admin"] = admin_username
        else:
            st.error("❌ Invalid username or password!")

if "user" in st.session_state or "admin" in st.session_state:
    user_email = st.session_state.get("user", {}).get("email", "")
    role = get_user_info(user_email)[0]
    st.subheader(f"Welcome, {user_email} ({role})")
    
    cert_type = st.selectbox("Select Certificate Type", ["Certificate of Achievement", "Backlog Certificate", "Attendance Certificate"])
    
    if st.button("Generate Certificate"):
        pdf_buffer = generate_certificate(user_email, role, cert_type)
        st.download_button("📄 Download Certificate", pdf_buffer, f"{cert_type}.pdf", "application/pdf")
