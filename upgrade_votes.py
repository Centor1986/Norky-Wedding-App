import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

try:
    cursor.execute("ALTER TABLE predrinks_requests ADD COLUMN votes INTEGER DEFAULT 1")
    print("Added votes column.")
except sqlite3.OperationalError:
    print("votes column already exists.")

connection.commit()
connection.close()

print("Votes upgrade complete.")