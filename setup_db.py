import sqlite3

connection = sqlite3.connect("norky_wedding.db")

cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS predrinks_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_name TEXT NOT NULL,
    song_title TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS reception_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_name TEXT NOT NULL,
    song_title TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

connection.commit()
connection.close()

print("Database created successfully.")