import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

# FORMALITIES TABLE

cursor.execute("""
CREATE TABLE IF NOT EXISTS formalities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    category TEXT NOT NULL,
    song_title TEXT,
    artist_name TEXT,
    notes TEXT,
    not_applicable INTEGER DEFAULT 0
)
""")

# MUST PLAY SONGS

cursor.execute("""
CREATE TABLE IF NOT EXISTS must_play (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    song_title TEXT NOT NULL,
    artist_name TEXT,
    notes TEXT
)
""")

# DO NOT PLAY SONGS

cursor.execute("""
CREATE TABLE IF NOT EXISTS do_not_play (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    song_title TEXT NOT NULL,
    artist_name TEXT,
    notes TEXT
)
""")

# VIBE PREFERENCES

cursor.execute("""
CREATE TABLE IF NOT EXISTS vibe_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    preference_name TEXT NOT NULL,
    enabled INTEGER DEFAULT 0
)
""")

# INSERT DEFAULT VIBE OPTIONS

default_preferences = [
    "Afrikaans Sokkie",
    "Commercial Dance",
    "80s Classics",
    "90s Throwbacks",
    "2000s Hits",
    "House Music",
    "R&B",
    "Hip-Hop",
    "Slow Dance Songs",
    "Family Friendly",
    "No Explicit Music",
    "Rock Classics",
    "Old School",
    "Line Dances"
]

for preference in default_preferences:

    cursor.execute("""
    INSERT OR IGNORE INTO vibe_preferences
    (id, preference_name, enabled)
    VALUES (
        (SELECT id FROM vibe_preferences
         WHERE preference_name = ?),
        ?,
        0
    )
    """, (preference, preference))

# INSERT DEFAULT FORMALITIES

default_formalities = [
    "Guest Arrival",
    "Bridal Party Entrance",
    "Bride Entrance",
    "Signing Song",
    "Ceremony Exit",
    "Reception Entrance",
    "First Dance",
    "Father Daughter Dance",
    "Mother Son Dance",
    "Cake Cutting",
    "Bouquet Toss",
    "Garter Toss",
    "Last Dance"
]

for formality in default_formalities:

    existing = cursor.execute("""
    SELECT * FROM formalities
    WHERE category = ?
    """, (formality,)).fetchone()

    if not existing:

        cursor.execute("""
        INSERT INTO formalities
        (category, song_title, artist_name, notes, not_applicable)
        VALUES (?, '', '', '', 0)
        """, (formality,))

connection.commit()
connection.close()

print("Formalities system created successfully.")