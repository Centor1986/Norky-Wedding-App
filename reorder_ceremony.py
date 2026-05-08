import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

ordered_items = [
    "Groom and Groomsmen Entrance",
    "Ring Bearer Entrance",
    "Bridal Party Entrance",
    "Bride Entrance",
    "Signing Song",
    "Ceremony Exit"
]

cursor.execute("""
DELETE FROM formalities
WHERE section = 'Ceremony'
""")

for item in ordered_items:
    cursor.execute("""
        INSERT INTO formalities
        (category, song_title, artist_name, youtube_link, notes, not_applicable, section)
        VALUES (?, '', '', '', '', 0, 'Ceremony')
    """, (item,))

connection.commit()
connection.close()

print("Ceremony order updated successfully.")