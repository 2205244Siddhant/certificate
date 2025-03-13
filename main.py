import streamlit as st
import requests
import sqlite3
from requests_oauthlib import OAuth2Session
from PIL import Image
from io import BytesIO
from datetime import datetime, timedelta

# Google OAuth2 Config
CLIENT_ID = "141742353498-5geiqu2biuf2s81klgau6qjsjve9fcrc.apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPX-jXVht-ctKWu6qjsjve9fZ3cE"
REDIRECT_URI = "https://certificate-generator-1.streamlit.app/"
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

# Connect to SQLite database
DB_PATH = "certificate.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Create users table if not exists
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        name TEXT,
        role TEXT DEFAULT 'Student',
        cert_type TEXT DEFAULT 'Participation',
        leave_days INTEGER DEFAULT 30
    )
''')

# Create leave requests table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT,
        start_date TEXT,
        end_date TEXT,
        days_requested INTEGER,
        status TEXT
    )
''')

conn.commit()

# Streamlit UI
st.title("\U0001F393 Google Sign-In & Certificate Generator + Leave Management")

# Step 1: Google OAuth2 Login
if "token" not in st.session_state:
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=["openid", "email", "profile"])
    authorization_url, state = google.authorization_url(AUTHORIZATION_BASE_URL, access_type="offline")
    st.session_state["oauth_state"] = state
    st.markdown(f"[Login with Google]({authorization_url})", unsafe_allow_html=True)

# Step 2: Handle OAuth Callback
if "code" in st.query_params:
    code = st.query_params["code"]
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, state=st.session_state["oauth_state"])
    
    try:
        token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, code=code)
        st.session_state["token"] = token
        
        # Fetch user info
        user_info = requests.get(USER_INFO_URL, headers={"Authorization": f"Bearer {token}"}).json()
        st.session_state["user"] = user_info
    except Exception as e:
        st.error(f"OAuth Error: {e}")

# Step 3: Display User Info & Handle Leave Requests
if "user" in st.session_state:
    user_email = st.session_state["user"]["email"]
    user_name = st.session_state["user"]["name"]
    
    st.subheader(f"Welcome, {user_email}")
    
    # Fetch user data
    cursor.execute("SELECT name, role, cert_type, leave_remaining FROM users WHERE email = ?", (user_email,))
    user = cursor.fetchone()
    
    if user:
        user_name, role, remaining_leaves, cert_type = user
    else:
        remaining_leaves = 30
        cursor.execute("INSERT INTO users (email, name, role, cert_type, leave_days) VALUES (?, ?, ?, ?)",
                       (user_email, st.session_state["user"]["name"], "Student", remaining_leaves))
        conn.commit()
        user_name = st.session_state["user"]["name"]
        role = "Student"
        cert_type = "Participation"
        st.success("User data saved.")

    st.write(f"**Your remaining leave days:** {remaining_leaves}")
    
    # Leave Application Form
    st.subheader("⏳ Apply for Leave")
    leave_start = st.date_input("Start Date")
    leave_end = st.date_input("End Date")
    
    if st.button("Apply for Leave"):
        if leave_start and leave_end:
            days_requested = (leave_end - leave_start).days + 1
            if days_requested > remaining_leaves:
                st.error("Insufficient leave balance!")
            else:
                new_balance = remaining_leaves - days_requested
                cursor.execute("UPDATE users SET leave_remaining = ? WHERE email = ?", (new_balance, user_email))
                cursor.execute("INSERT INTO leave_requests (email, days_requested, status) VALUES (?, ?, ?)", 
                               (user_email, days_requested, "Approved"))
                conn.commit()
                st.success(f"Leave approved! Your new leave balance: {new_balance} days")

    # Generate Certificate Section
    st.subheader("\ud83c\udf93 Generate Your Certificate")
    name = st.text_input("Enter Your Name", value=user_name)
    
    if st.button("Generate Your Certificate"):
        pdf_buffer = BytesIO()
        c = canvas.Canvas(pdf_buffer)
        c.setFont("Helvetica", 30)
        c.drawString(200, 700, f"Certificate of {cert_type}")
        c.setFont("Helvetica", 20)
        c.drawString(220, 650, f"Awarded to: {name}")
        c.setFont("Helvetica", 16)
        c.drawString(200, 600, f"Issued on: {datetime.today().strftime('%Y-%m-%d')}")
        c.save()
        
        pdf_buffer = BytesIO()
        pdf_buffer.seek(0)
        st.download_button(label="📄 Download Certificate", data=pdf_buffer, file_name="certificate.pdf", mime="application/pdf")

conn.close()
