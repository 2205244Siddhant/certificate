import streamlit as st
import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BACKEND_URL = "http://127.0.0.1:5000"

# ✅ Login Page
def login():
    st.title("🔑 Login to AI Academic System")
    username = st.text_input("Enter your username:")
    role = st.selectbox("Select your role:", ["Student", "Mentor", "Admin"])

    if st.button("Login") and username:
        st.session_state["username"] = username
        st.session_state["role"] = role
        st.session_state["logged_in"] = True
        st.experimental_set_query_params(role=role)  # Persist state

# ✅ Student Dashboard
def student_dashboard():
    st.title("🎓 Student Dashboard")
    st.write(f"👋 Welcome, {st.session_state['username']}")

    # 📚 Ask an Academic Question
    st.subheader("📚 Ask an Academic Question")
    question = st.text_input("Enter your question:")
    if st.button("Ask"):
        response = requests.post(f"{BACKEND_URL}/academic", json={"student_id": st.session_state["username"], "query": question})
        if response.status_code == 200:
            st.success(response.json().get("response", "❌ Error processing AI response."))
        else:
            st.error("❌ AI Error. Please try again.")

    # 📝 Request Leave
    st.subheader("📝 Request Leave")
    leave_days = st.number_input("Number of Leave Days", min_value=1, step=1)
    if st.button("Apply Leave"):
        response = requests.post(f"{BACKEND_URL}/leave", json={"student_id": st.session_state["username"], "days": leave_days})
        if response.status_code == 200:
            st.success(response.json().get("message", "❌ Error processing response."))
        else:
            st.error("❌ Backend error.")

    # 📌 Leave Status
    st.subheader("📌 Your Leave Requests")
    response = requests.get(f"{BACKEND_URL}/student-leave-status", params={"student_id": st.session_state["username"]})

    if response.status_code == 200:
        leave_requests = response.json().get("requests", [])
        if leave_requests:
            for req in leave_requests:
                st.write(f"📌 **Mentor:** {req['mentor_id']} | **Days:** {req['days']} | **Status:** {req['status']}")
        else:
            st.write("No leave requests found.")
    else:
        st.error("❌ Error fetching leave status.")

    # 📜 Generate Certificate
    st.subheader("📜 Generate Certificate")
    cert_type = st.selectbox("Select Certificate Type:", ["Bonafide", "NOC"])
    if st.button("Generate Certificate"):
        response = requests.post(f"{BACKEND_URL}/certificate", json={"student_id": st.session_state["username"], "type": cert_type})
        if response.status_code == 200:
            st.success("✅ Certificate generated successfully!")
            st.download_button("Download Certificate", response.content, file_name=f"{st.session_state['username']}_certificate.pdf", mime="application/pdf")
        else:
            st.error("❌ Error generating certificate.")

# ✅ Mentor Dashboard
def mentor_dashboard():
    st.title("👨‍🏫 Mentor Dashboard")
    st.write(f"👋 Welcome, {st.session_state['username']}")

    # 📌 Leave Requests
    st.subheader("📌 Pending Leave Requests")
    response = requests.get(f"{BACKEND_URL}/mentor-leave-requests", params={"mentor_id": st.session_state["username"]})

    if response.status_code == 200:
        leave_requests = response.json().get("requests", [])
        if leave_requests:
            for req in leave_requests:
                st.write(f"📌 **Student:** {req['student_id']} | **Days:** {req['days']} | **Status:** {req['status']}")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"✅ Approve {req['id']}"):
                        requests.post(f"{BACKEND_URL}/approve-leave", json={"leave_id": req["id"]})
                        st.success("✅ Leave Approved!")
                with col2:
                    if st.button(f"❌ Reject {req['id']}"):
                        requests.post(f"{BACKEND_URL}/reject-leave", json={"leave_id": req["id"]})
                        st.error("❌ Leave Rejected!")
        else:
            st.write("No pending leave requests.")
    else:
        st.error("❌ Error fetching leave requests.")

# ✅ Admin Dashboard
def admin_dashboard():
    st.title("⚙️ Admin Dashboard")

    # 📂 Upload AI Training Data
    st.subheader("📂 Upload AI Training Data (JSON/CSV/Excel/PDF)")
    uploaded_file = st.file_uploader("Upload JSON/CSV/Excel/PDF File", type=["csv", "xlsx", "json", "pdf"])
    if uploaded_file and st.button("Upload"):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
        response = requests.post(f"{BACKEND_URL}/upload-data", files=files)
        if response.status_code == 200:
            st.success(response.json().get("message", "✅ File uploaded successfully!"))
        else:
            st.error("❌ Error processing file.")

    # 👨‍🏫 Assign Mentors
    st.subheader("👨‍🏫 Assign Mentors to Students")
    student_id = st.text_input("Enter Student ID:")
    mentor_id = st.text_input("Enter Mentor ID:")
    if st.button("Assign Mentor"):
        response = requests.post(f"{BACKEND_URL}/assign-mentor", json={"student_id": student_id, "mentor_id": mentor_id})
        if response.status_code == 200:
            st.success(response.json().get("message", "✅ Mentor assigned successfully!"))
        else:
            st.error("❌ Error assigning mentor.")

# ✅ Main App Logic
if "logged_in" not in st.session_state:
    login()
else:
    role = st.session_state["role"]
    if role == "Student":
        student_dashboard()
    elif role == "Mentor":
        mentor_dashboard()
    elif role == "Admin":
        admin_dashboard()
