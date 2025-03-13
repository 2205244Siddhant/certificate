import sqlite3

# Connect to SQLite database (or create if it doesn't exist)
conn = sqlite3.connect("certificate.db")
cursor = conn.cursor()

# Create users table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    cert_type TEXT NOT NULL
)
""")

# Insert sample data
cursor.executemany("""
INSERT INTO users (name, role, cert_type) VALUES (?, ?, ?)
""", [
    ('Alice Johnson', 'Student', 'Bonafide'),
    ('Bob Smith', 'Employee', 'NOC'),
    ('Charlie Brown', 'Faculty', 'Experience')
])

conn.commit()
conn.close()

print("Database initialized successfully!")
