import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

columns_to_add = [
    ("formalities", "youtube_link"),
    ("must_play", "youtube_link"),
    ("do_not_play", "youtube_link")
]

for table, column in columns_to_add:
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT DEFAULT ''")
        print(f"Added {column} to {table}.")
    except sqlite3.OperationalError:
        print(f"{column} already exists in {table}.")

connection.commit()
connection.close()

print("YouTube reference fields added successfully.")