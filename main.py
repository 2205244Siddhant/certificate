import streamlit as st
import requests
from requests_oauthlib import OAuth2Session
from PIL import Image
from io import BytesIO
from reportlab.pdfgen import canvas
import sqlite3
from datetime import datetime

# Google OAuth2 Config
CLIENT_ID = "141742353498-5geiqu2biuf2s81klgau6qjsjve9fcrc.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "https://certificate-generator-1.streamlit.app/"
AUTHORIZATION_BASE_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USER_INFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"

# Database setup
conn = sqlite3.connect("students.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    email TEXT PRIMARY KEY,
    name TEXT,
    remaining_leaves INTEGER DEFAULT 30
)
""")
conn.commit()

# Streamlit UI
st.title("🎓 Google Sign-In & Certificate Generator & Leave Request")

# Step 1: Generate Google OAuth2 Login URL
if "token" not in st.session_state:
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, scope=["email", "profile"])
    authorization_url, state = google.authorization_url(AUTHORIZATION_BASE_URL, access_type="offline")
    st.session_state["oauth_state"] = state
    st.markdown(f"[🔑 Sign in with Google]({authorization_url})")

# Step 2: Handle OAuth Callback
if "code" in st.query_params and "token" not in st.session_state:
    code = st.query_params["code"]
    google = OAuth2Session(CLIENT_ID, redirect_uri=REDIRECT_URI, state=st.session_state.get("oauth_state"))
    
    try:
        token = google.fetch_token(TOKEN_URL, client_secret=CLIENT_SECRET, code=code)
        st.session_state["token"] = token

        # Fetch user info
        user_info = requests.get(USER_INFO_URL, headers={"Authorization": f"Bearer {token['access_token']}"}).json()
        st.session_state["user"] = user_info

        # Check if user exists in DB, if not, create an entry with 30 leaves
        with sqlite3.connect("database.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT remaining_leaves FROM students WHERE email=?", (user_info["email"],))
            result = cursor.fetchone()

            if result is None:
                cursor.execute("INSERT INTO students (email, name, remaining_leaves) VALUES (?, ?, ?)", 
                               (user_info["email"], user_info["name"], 30))
                conn.commit()

    except Exception as e:
        st.error(f"OAuth Error: {e}")

# Step 3: Display User Info & Features After Login
if "user" in st.session_state:
    user_info = st.session_state["user"]
    st.title("🎓 Google Sign-In & Certificate Generator")
    
    # Show user info
    st.success(f"Welcome, {user_info['name']}!")
    st.image(user_info.get("picture", ""), width=100)

    # Fetch remaining leaves from DB
    cursor.execute("SELECT remaining_leaves FROM students WHERE email=?", (user_info["email"],))
    result = cursor.fetchone()
    remaining_leaves = result[0] if result else 30

    st.subheader("🗓️ Request Leave")
    st.write(f"Remaining Leaves: **{remaining_leaves} days**")
    
    leave_start = st.date_input("Start Date")
    leave_end = st.date_input("End Date")

    if st.button("Request Leave"):
        if leave_start and leave_end:
            leave_days = (leave_end - leave_start).days + 1  # Include the start day
            if leave_start > leave_end:
                st.error("Error: End date must be after start date.")
            elif remaining_leaves >= leave_end.day - leave_start.day + 1:
                new_leave_balance = remaining_leaves - leave_days
                cursor.execute("UPDATE students SET remaining_leaves=? WHERE email=?", 
                               (remaining_leaves - (leave_end.day - leave_start.day + 1), user_info["email"]))
                conn.commit()
                st.success(f"Leave approved! You have {remaining_leaves - (leave_end.day - leave_start.day + 1)} days remaining.")
            else:
                st.error(f"You only have {remaining_leaves} leave days left. Request denied.")

    # Certificate Generator
    st.subheader("🎓 Generate Your Certificate")
    name = st.text_input("Enter Your Name", value=user_info["name"])
    
    if st.button("Generate Your Certificate"):
        buffer = BytesIO()
        p = canvas.Canvas(buffer)
        p.drawString(200, 700, "Certificate of Achievement")
        p.drawString(220, 650, f"Awarded to: {name}")
        p.showPage()
        p.save()

        buffer.seek(0)
        st.download_button(
            label="📜 Download Certificate",
            data=buffer,
            file_name="certificate.pdf",
            mime="application/pdf"
        )

conn.close()
