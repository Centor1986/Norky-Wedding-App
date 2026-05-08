import sqlite3

connection = sqlite3.connect("norky_wedding.db")
cursor = connection.cursor()

cursor.execute("""
DELETE FROM formalities
WHERE category = 'Guest Arrival'
AND section = 'Ceremony'
""")

connection.commit()
connection.close()

print("Guest Arrival removed from Ceremony Music.")