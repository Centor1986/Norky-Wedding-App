import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

new_items = [
    "Ring Bearer Entrance",
    "Groom and Groomsmen Entrance"
]

for item in new_items:
    existing = cursor.execute("""
        SELECT id FROM formalities
        WHERE category = ?
        AND section = 'Ceremony'
    """, (item,)).fetchone()

    if not existing:
        cursor.execute("""
            INSERT INTO formalities
            (category, song_title, artist_name, youtube_link, notes, not_applicable, section)
            VALUES (?, '', '', '', '', 0, 'Ceremony')
        """, (item,))

connection.commit()
connection.close()

print("New ceremony entries added successfully.")