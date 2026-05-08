from flask import Flask, render_template, request, redirect, flash, session, jsonify, send_file
import sqlite3
import os
import qrcode
import requests
from datetime import datetime, date, timedelta
from functools import wraps

from dotenv import load_dotenv
from spotify_setup import create_spotify_oauth, get_spotify_client_from_token
from pdf_export import generate_formalities_pdf

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "norky-secret-key")

PLAYLIST_ID = os.getenv("SPOTIFY_PREDRINKS_PLAYLIST_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "norky123"
)

COUPLE_PASSWORD = os.getenv(
    "COUPLE_PASSWORD",
    "wedding123"
)


# =========================
# DATABASE
# =========================

def get_db_connection():

    connection = sqlite3.connect(
        "norky_wedding.db"
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    connection = get_db_connection()

    cursor = connection.cursor()

    # =========================
    # WEDDINGS TABLE
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        couple_names TEXT NOT NULL,
        wedding_date TEXT NOT NULL UNIQUE,
        venue_name TEXT,
        couple_password TEXT NOT NULL,
        spotify_playlist_id TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =========================
    # SETTINGS
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wedding_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        couple_names TEXT,
        wedding_date TEXT,
        venue_name TEXT,
        welcome_message TEXT,
        facebook_link TEXT,
        instagram_link TEXT,
        tiktok_link TEXT,
        couple_portal_locked INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO wedding_settings
    (
        id,
        couple_names,
        wedding_date,
        venue_name,
        welcome_message,
        facebook_link,
        instagram_link,
        tiktok_link,
        couple_portal_locked
    )
    VALUES
    (
        1,
        'Ashley & Matthew',
        '',
        'Deannie Landgoed',
        'Welcome to our wedding experience.',
        '#',
        '#',
        '#',
        0
    )
    """)

    # =========================
    # REQUESTS
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predrinks_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT,
        song_title TEXT,
        artist_name TEXT,
        track_uri TEXT,
        votes INTEGER DEFAULT 1,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reception_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT,
        song_title TEXT,
        artist_name TEXT,
        status TEXT DEFAULT 'pending',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT,
        song_title TEXT,
        artist_name TEXT,
        action TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # =========================
    # FORMALITIES
    # =========================

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS formalities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        song_title TEXT,
        artist_name TEXT,
        youtube_link TEXT,
        notes TEXT,
        not_applicable INTEGER DEFAULT 0,
        section TEXT DEFAULT 'Reception',
        prep_status TEXT DEFAULT 'Pending Download'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ceremony_extra_songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_title TEXT,
        artist_name TEXT,
        youtube_link TEXT,
        notes TEXT,
        prep_status TEXT DEFAULT 'Pending Download'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS must_play (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_title TEXT,
        artist_name TEXT,
        youtube_link TEXT,
        notes TEXT,
        prep_status TEXT DEFAULT 'Pending Download'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS do_not_play (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_title TEXT,
        artist_name TEXT,
        youtube_link TEXT,
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vibe_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        preference_name TEXT UNIQUE,
        enabled INTEGER DEFAULT 0
    )
    """)

    # =========================
    # DEFAULT FORMALITIES
    # =========================

    ceremony_items = [
        "Groom and Groomsmen Entrance",
        "Ring Bearer Entrance",
        "Bridal Party Entrance",
        "Bride Entrance",
        "Signing Song",
        "Ceremony Exit"
    ]

    reception_items = [
        "Reception Entrance",
        "First Dance",
        "Father Daughter Dance",
        "Mother Son Dance",
        "Cake Cutting",
        "Bouquet Toss",
        "Garter Toss",
        "Last Dance"
    ]

    for item in ceremony_items:

        existing = cursor.execute("""
        SELECT id
        FROM formalities
        WHERE category = ?
        AND section = 'Ceremony'
        """, (item,)).fetchone()

        if not existing:

            cursor.execute("""
            INSERT INTO formalities
            (
                category,
                song_title,
                artist_name,
                youtube_link,
                notes,
                not_applicable,
                section,
                prep_status
            )
            VALUES
            (?, '', '', '', '', 0, 'Ceremony', 'Pending Download')
            """, (item,))

    for item in reception_items:

        existing = cursor.execute("""
        SELECT id
        FROM formalities
        WHERE category = ?
        AND section = 'Reception'
        """, (item,)).fetchone()

        if not existing:

            cursor.execute("""
            INSERT INTO formalities
            (
                category,
                song_title,
                artist_name,
                youtube_link,
                notes,
                not_applicable,
                section,
                prep_status
            )
            VALUES
            (?, '', '', '', '', 0, 'Reception', 'Pending Download')
            """, (item,))

    # =========================
    # DEFAULT VIBES
    # =========================

    vibe_options = [
        "Afrikaans Sokkie",
        "Commercial Dance",
        "80s Classics",
        "90s Throwbacks",
        "2000s Hits",
        "House Music",
        "R&B",
        "Hip-Hop",
        "Slow Dance Songs",
        "Family Friendly",
        "No Explicit Music",
        "Rock Classics",
        "Old School",
        "Line Dances"
    ]

    for vibe in vibe_options:

        cursor.execute("""
        INSERT OR IGNORE INTO vibe_preferences
        (
            preference_name,
            enabled
        )
        VALUES
        (?, 0)
        """, (vibe,))

    connection.commit()
    connection.close()


init_database()


# =========================
# HELPERS
# =========================

def get_wedding_settings():

    connection = get_db_connection()

    settings = connection.execute("""
    SELECT *
    FROM wedding_settings
    WHERE id = 1
    """).fetchone()

    connection.close()

    return settings


def admin_required(f):

    @wraps(f)

    def decorated_function(*args, **kwargs):

        if not session.get("admin_logged_in"):

            return redirect("/admin-login")

        return f(*args, **kwargs)

    return decorated_function


def couple_required(f):

    @wraps(f)

    def decorated_function(*args, **kwargs):

        if not session.get("couple_logged_in"):

            return redirect("/couple-login")

        return f(*args, **kwargs)

    return decorated_function


def parse_wedding_date(date_text):

    if not date_text:
        return None

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %B %Y",
        "%d %b %Y"
    ]

    for fmt in formats:

        try:

            return datetime.strptime(
                date_text.strip(),
                fmt
            ).date()

        except ValueError:
            pass

    return None


def is_couple_portal_locked(settings):

    if not settings:
        return False

    try:

        if settings["couple_portal_locked"] == 1:
            return True

    except Exception:
        pass

    wedding_date = parse_wedding_date(
        settings["wedding_date"]
    )

    if not wedding_date:
        return False

    return (
        date.today()
        >= wedding_date - timedelta(days=1)
    )


def generate_qr_code():

    os.makedirs(
        os.path.join("static", "qr"),
        exist_ok=True
    )

    qr_path = os.path.join(
        "static",
        "qr",
        "wedding_qr.png"
    )

    url = os.getenv(
        "PUBLIC_APP_URL",
        "https://norky-wedding-app.onrender.com/"
    )

    img = qrcode.make(url)

    img.save(qr_path)

    return "/static/qr/wedding_qr.png"


# =========================
# AUTH
# =========================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        password = request.form["password"]

        if password == ADMIN_PASSWORD:

            session["admin_logged_in"] = True

            flash("Admin login successful.")

            return redirect("/admin")

        flash("Incorrect password.")

    return render_template(
        "admin_login.html"
    )


@app.route("/admin-logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    flash("Logged out successfully.")

    return redirect("/")


@app.route("/couple-login", methods=["GET", "POST"])
def couple_login():

    if request.method == "POST":

        password = request.form["password"]

        if password == COUPLE_PASSWORD:

            session["couple_logged_in"] = True

            flash("Couple login successful.")

            return redirect("/couple")

        flash("Incorrect couple password.")

    return render_template(
        "couple_login.html"
    )


@app.route("/couple-logout")
def couple_logout():

    session.pop(
        "couple_logged_in",
        None
    )

    flash("Couple logged out successfully.")

    return redirect("/")


# =========================
# MAIN ROUTES
# =========================

@app.route("/")
def landing():

    settings = get_wedding_settings()

    return render_template(
        "landing.html",
        settings=settings
    )


@app.route("/admin/weddings", methods=["GET", "POST"])
@admin_required
def manage_weddings():

    connection = get_db_connection()

    if request.method == "POST":

        couple_names = request.form["couple_names"]
        wedding_date = request.form["wedding_date"]
        venue_name = request.form["venue_name"]
        couple_password = request.form["couple_password"]

        existing = connection.execute("""
        SELECT *
        FROM weddings
        WHERE wedding_date = ?
        """, (
            wedding_date,
        )).fetchone()

        if existing:

            flash(
                "This wedding date is already booked."
            )

            return redirect("/admin/weddings")

        connection.execute("""
        INSERT INTO weddings
        (
            couple_names,
            wedding_date,
            venue_name,
            couple_password
        )
        VALUES (?, ?, ?, ?)
        """, (
            couple_names,
            wedding_date,
            venue_name,
            couple_password
        ))

        connection.commit()

        flash(
            "Wedding added successfully."
        )

        return redirect("/admin/weddings")

    weddings = connection.execute("""
    SELECT *
    FROM weddings
    ORDER BY wedding_date ASC
    """).fetchall()

    connection.close()

    return render_template(
        "manage_weddings.html",
        weddings=weddings
    )


@app.route("/admin")
@admin_required
def admin():

    settings = get_wedding_settings()

    return render_template(
        "admin.html",
        settings=settings
    )


@app.route("/couple")
@couple_required
def couple_portal():

    settings = get_wedding_settings()

    portal_locked = is_couple_portal_locked(
        settings
    )

    return render_template(
        "couple.html",
        settings=settings,
        portal_locked=portal_locked
    )


@app.route("/predrinks")
def predrinks():

    settings = get_wedding_settings()

    return render_template(
        "predrinks.html",
        settings=settings
    )


@app.route("/reception")
def reception():

    settings = get_wedding_settings()

    return render_template(
        "reception.html",
        settings=settings
    )


@app.route("/qr")
@admin_required
def qr_page():

    qr_image = generate_qr_code()

    settings = get_wedding_settings()

    return render_template(
        "qr.html",
        qr_image=qr_image,
        settings=settings
    )


# =========================
# RUN
# =========================

if __name__ == "__main__":

    app.run(debug=True)