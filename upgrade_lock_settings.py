import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

try:
    cursor.execute("ALTER TABLE wedding_settings ADD COLUMN couple_portal_locked INTEGER DEFAULT 0")
    print("Added couple_portal_locked.")
except sqlite3.OperationalError:
    print("couple_portal_locked already exists.")

connection.commit()
connection.close()

print("Lock settings upgrade complete.")