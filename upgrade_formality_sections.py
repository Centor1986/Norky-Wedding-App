import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

# Add section column if it does not exist
try:
    cursor.execute("ALTER TABLE formalities ADD COLUMN section TEXT DEFAULT 'Reception'")
    print("Added section column.")
except sqlite3.OperationalError:
    print("section column already exists.")

# Clear current formalities and rebuild cleanly
cursor.execute("DELETE FROM formalities")

ceremony_formalities = [
    "Guest Arrival",
    "Bridal Party Entrance",
    "Bride Entrance",
    "Signing Song",
    "Ceremony Exit"
]

reception_formalities = [
    "Reception Entrance",
    "First Dance",
    "Father Daughter Dance",
    "Mother Son Dance",
    "Cake Cutting",
    "Bouquet Toss",
    "Garter Toss",
    "Last Dance"
]

for item in ceremony_formalities:
    cursor.execute("""
    INSERT INTO formalities
    (category, song_title, artist_name, notes, not_applicable, section)
    VALUES (?, '', '', '', 0, 'Ceremony')
    """, (item,))

for item in reception_formalities:
    cursor.execute("""
    INSERT INTO formalities
    (category, song_title, artist_name, notes, not_applicable, section)
    VALUES (?, '', '', '', 0, 'Reception')
    """, (item,))

connection.commit()
connection.close()

print("Formalities split into Ceremony and Reception successfully.")