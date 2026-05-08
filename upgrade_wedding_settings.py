import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS wedding_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    couple_names TEXT NOT NULL,
    wedding_date TEXT,
    venue_name TEXT,
    welcome_message TEXT,
    facebook_link TEXT,
    instagram_link TEXT,
    tiktok_link TEXT
)
""")

cursor.execute("""
INSERT OR IGNORE INTO wedding_settings
(id, couple_names, wedding_date, venue_name, welcome_message, facebook_link, instagram_link, tiktok_link)
VALUES
(1, 'Ashley & Matthew', 'Wedding Celebration', 'Deannie Landgoed',
'Welcome to our wedding celebration. Scan below to request songs, vote for music, and join the vibe.',
'https://www.facebook.com/NorkyWeddingMedia', '#', '#')
""")

connection.commit()
connection.close()

print("Wedding settings table created successfully.")