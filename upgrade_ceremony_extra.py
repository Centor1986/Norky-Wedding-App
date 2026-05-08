import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS ceremony_extra_songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_title TEXT NOT NULL,
    artist_name TEXT,
    youtube_link TEXT,
    notes TEXT
)
""")

connection.commit()
connection.close()

print("Extra ceremony songs table created successfully.")