import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_name TEXT NOT NULL,
    song_title TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

connection.commit()
connection.close()

print("Activity log table created successfully.")