import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS weddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    couple_names TEXT NOT NULL,
    wedding_date TEXT NOT NULL UNIQUE,
    venue_name TEXT,
    couple_password TEXT NOT NULL,
    spotify_playlist_id TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

connection.commit()
connection.close()

print("Weddings table created successfully.")
print("Wedding dates are now protected from duplicate bookings.")