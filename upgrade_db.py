import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

try:
    cursor.execute("ALTER TABLE predrinks_requests ADD COLUMN track_uri TEXT")
    print("Added track_uri to predrinks_requests.")
except sqlite3.OperationalError:
    print("track_uri already exists.")

connection.commit()
connection.close()

print("Database upgrade complete.")