import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

tables = [
    "formalities",
    "ceremony_extra_songs",
    "must_play"
]

for table in tables:
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN prep_status TEXT DEFAULT 'Pending Download'")
        print(f"Added prep_status to {table}.")
    except sqlite3.OperationalError:
        print(f"prep_status already exists in {table}.")

connection.commit()
connection.close()

print("Prep status system added successfully.")