import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

try:
    cursor.execute("ALTER TABLE reception_requests ADD COLUMN youtube_link TEXT DEFAULT ''")
    print("Added youtube_link to reception_requests.")
except sqlite3.OperationalError:
    print("youtube_link already exists in reception_requests.")

connection.commit()
connection.close()

print("Reception YouTube upgrade complete.")