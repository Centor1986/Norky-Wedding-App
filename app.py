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
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "norky123")


# =========================
# DATABASE SETUP
# =========================

def get_db_connection():
    connection = sqlite3.connect("norky_wedding.db")
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS wedding_settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        couple_names TEXT NOT NULL,
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
    (id, couple_names, wedding_date, venue_name, welcome_message, facebook_link, instagram_link, tiktok_link, couple_portal_locked)
    VALUES
    (1, 'Ashley & Matthew', 'Wedding Celebration', 'Deannie Landgoed',
    'Welcome to our wedding celebration. Scan below to request songs, vote for music, and join the vibe.',
    '#', '#', '#', 0)
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS predrinks_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT NOT NULL,
        song_title TEXT NOT NULL,
        artist_name TEXT NOT NULL,
        track_uri TEXT,
        votes INTEGER DEFAULT 1,
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reception_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT NOT NULL,
        song_title TEXT NOT NULL,
        artist_name TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT NOT NULL,
        song_title TEXT NOT NULL,
        artist_name TEXT NOT NULL,
        action TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS formalities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        song_title TEXT,
        artist_name TEXT,
        youtube_link TEXT DEFAULT '',
        notes TEXT,
        not_applicable INTEGER DEFAULT 0,
        section TEXT DEFAULT 'Reception',
        prep_status TEXT DEFAULT 'Pending Download'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ceremony_extra_songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_title TEXT NOT NULL,
        artist_name TEXT,
        youtube_link TEXT,
        notes TEXT,
        prep_status TEXT DEFAULT 'Pending Download'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS must_play (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_title TEXT NOT NULL,
        artist_name TEXT,
        youtube_link TEXT DEFAULT '',
        notes TEXT,
        prep_status TEXT DEFAULT 'Pending Download'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS do_not_play (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        song_title TEXT NOT NULL,
        artist_name TEXT,
        youtube_link TEXT DEFAULT '',
        notes TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vibe_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        preference_name TEXT NOT NULL UNIQUE,
        enabled INTEGER DEFAULT 0
    )
    """)

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
        existing = cursor.execute(
            "SELECT id FROM formalities WHERE category = ? AND section = 'Ceremony'",
            (item,)
        ).fetchone()

        if not existing:
            cursor.execute("""
            INSERT INTO formalities
            (category, song_title, artist_name, youtube_link, notes, not_applicable, section, prep_status)
            VALUES (?, '', '', '', '', 0, 'Ceremony', 'Pending Download')
            """, (item,))

    for item in reception_items:
        existing = cursor.execute(
            "SELECT id FROM formalities WHERE category = ? AND section = 'Reception'",
            (item,)
        ).fetchone()

        if not existing:
            cursor.execute("""
            INSERT INTO formalities
            (category, song_title, artist_name, youtube_link, notes, not_applicable, section, prep_status)
            VALUES (?, '', '', '', '', 0, 'Reception', 'Pending Download')
            """, (item,))

    vibes = [
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

    for vibe in vibes:
        cursor.execute("""
        INSERT OR IGNORE INTO vibe_preferences
        (preference_name, enabled)
        VALUES (?, 0)
        """, (vibe,))

    connection.commit()
    connection.close()


init_database()


# =========================
# HELPERS
# =========================

def get_wedding_settings():
    connection = get_db_connection()
    settings = connection.execute("SELECT * FROM wedding_settings WHERE id = 1").fetchone()
    connection.close()
    return settings


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect("/admin-login")
        return f(*args, **kwargs)
    return decorated_function


def parse_wedding_date(date_text):
    if not date_text:
        return None

    formats = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"]

    for fmt in formats:
        try:
            return datetime.strptime(date_text.strip(), fmt).date()
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

    wedding_date = parse_wedding_date(settings["wedding_date"])

    if not wedding_date:
        return False

    return date.today() >= wedding_date - timedelta(days=1)


def get_logged_in_spotify():
    token_info = session.get("spotify_token_info", None)

    if not token_info:
        return None

    return get_spotify_client_from_token(token_info)


def get_now_playing(sp):
    try:
        current = sp.current_user_playing_track()

        if not current or not current.get("item"):
            return None

        track = current["item"]

        return {
            "song_title": track["name"],
            "artist_name": track["artists"][0]["name"],
            "album_name": track["album"]["name"],
            "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else "",
            "is_playing": current.get("is_playing", False)
        }

    except Exception:
        return None


def youtube_search(query):
    if not query or not YOUTUBE_API_KEY:
        return []

    url = "https://www.googleapis.com/youtube/v3/search"

    params = {
        "part": "snippet",
        "q": query,
        "key": YOUTUBE_API_KEY,
        "maxResults": 8,
        "type": "video"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
    except Exception:
        return []

    results = []

    for item in data.get("items", []):
        video_id = item["id"]["videoId"]

        results.append({
            "title": item["snippet"]["title"],
            "channel": item["snippet"]["channelTitle"],
            "thumbnail": item["snippet"]["thumbnails"]["medium"]["url"],
            "youtube_link": f"https://www.youtube.com/watch?v={video_id}"
        })

    return results


def get_top_requested():
    connection = get_db_connection()

    top_requested = connection.execute("""
        SELECT *
        FROM predrinks_requests
        ORDER BY votes DESC, requested_at DESC
        LIMIT 5
    """).fetchall()

    connection.close()
    return top_requested


def get_recent_activity():
    connection = get_db_connection()

    recent_activity = connection.execute("""
        SELECT *
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT 8
    """).fetchall()

    connection.close()
    return recent_activity


def log_activity(guest_name, song_title, artist_name, action):
    connection = get_db_connection()

    connection.execute("""
        INSERT INTO activity_log
        (guest_name, song_title, artist_name, action)
        VALUES (?, ?, ?, ?)
    """, (guest_name, song_title, artist_name, action))

    connection.commit()
    connection.close()


def get_formalities_data():
    connection = get_db_connection()

    ceremony_formalities = connection.execute("""
        SELECT *
        FROM formalities
        WHERE section = 'Ceremony'
        AND category != 'Guest Arrival'
        ORDER BY id ASC
    """).fetchall()

    reception_formalities = connection.execute("""
        SELECT *
        FROM formalities
        WHERE section = 'Reception'
        ORDER BY id ASC
    """).fetchall()

    ceremony_extra_songs = connection.execute("""
        SELECT *
        FROM ceremony_extra_songs
        ORDER BY id DESC
    """).fetchall()

    must_play = connection.execute("""
        SELECT *
        FROM must_play
        ORDER BY id DESC
    """).fetchall()

    do_not_play = connection.execute("""
        SELECT *
        FROM do_not_play
        ORDER BY id DESC
    """).fetchall()

    vibe_preferences = connection.execute("""
        SELECT *
        FROM vibe_preferences
        ORDER BY id ASC
    """).fetchall()

    connection.close()

    return (
        ceremony_formalities,
        reception_formalities,
        ceremony_extra_songs,
        must_play,
        do_not_play,
        vibe_preferences
    )


def generate_qr_code():
    os.makedirs(os.path.join("static", "qr"), exist_ok=True)

    qr_path = os.path.join("static", "qr", "wedding_qr.png")
    url = os.getenv("PUBLIC_APP_URL", "http://127.0.0.1:5000/")

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

    return render_template("admin_login.html")


@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_logged_in", None)
    flash("Logged out successfully.")
    return redirect("/")


# =========================
# MAIN ROUTES
# =========================

@app.route("/")
def landing():
    settings = get_wedding_settings()
    return render_template("landing.html", settings=settings)


@app.route("/youtube-search-api")
def youtube_search_api():
    query = request.args.get("q", "").strip()
    results = youtube_search(query)
    return jsonify(results)


@app.route("/export-formalities-pdf")
@admin_required
def export_formalities_pdf():
    settings = get_wedding_settings()

    (
        ceremony_formalities,
        reception_formalities,
        ceremony_extra_songs,
        must_play,
        do_not_play,
        vibe_preferences
    ) = get_formalities_data()

    pdf_path = os.path.join("static", "formalities_export.pdf")

    generate_formalities_pdf(
        pdf_path,
        settings,
        ceremony_formalities,
        reception_formalities,
        ceremony_extra_songs,
        must_play,
        do_not_play,
        vibe_preferences
    )

    return send_file(pdf_path, as_attachment=True)


@app.route("/settings", methods=["GET", "POST"])
@admin_required
def wedding_settings():
    connection = get_db_connection()

    if request.method == "POST":
        connection.execute("""
            UPDATE wedding_settings
            SET
                couple_names = ?,
                wedding_date = ?,
                venue_name = ?,
                welcome_message = ?,
                facebook_link = ?,
                instagram_link = ?,
                tiktok_link = ?
            WHERE id = 1
        """, (
            request.form["couple_names"],
            request.form["wedding_date"],
            request.form["venue_name"],
            request.form["welcome_message"],
            request.form["facebook_link"],
            request.form["instagram_link"],
            request.form["tiktok_link"]
        ))

        connection.commit()
        flash("Wedding settings updated successfully.")

    settings = connection.execute("SELECT * FROM wedding_settings WHERE id = 1").fetchone()
    connection.close()

    return render_template("settings.html", settings=settings)


@app.route("/couple", methods=["GET", "POST"])
def couple_portal():
    settings = get_wedding_settings()
    portal_locked = is_couple_portal_locked(settings)

    if request.method == "POST":
        if portal_locked:
            flash("The couple portal is locked. Please contact Norky directly for urgent changes.")
            return redirect("/couple")

        connection = get_db_connection()

        formalities = connection.execute("SELECT * FROM formalities ORDER BY id ASC").fetchall()

        for item in formalities:
            formality_id = item["id"]

            connection.execute("""
                UPDATE formalities
                SET
                    song_title = ?,
                    artist_name = ?,
                    youtube_link = ?,
                    notes = ?,
                    not_applicable = ?
                WHERE id = ?
            """, (
                request.form.get(f"song_title_{formality_id}", ""),
                request.form.get(f"artist_name_{formality_id}", ""),
                request.form.get(f"youtube_link_{formality_id}", ""),
                request.form.get(f"notes_{formality_id}", ""),
                1 if request.form.get(f"not_applicable_{formality_id}") == "on" else 0,
                formality_id
            ))

        extra_song_titles = request.form.getlist("extra_song_title[]")
        extra_artist_names = request.form.getlist("extra_artist_name[]")
        extra_youtube_links = request.form.getlist("extra_youtube_link[]")
        extra_notes = request.form.getlist("extra_notes[]")

        for i in range(len(extra_song_titles)):
            song_title = extra_song_titles[i].strip()

            artist_name = extra_artist_names[i].strip() if i < len(extra_artist_names) else ""
            youtube_link = extra_youtube_links[i].strip() if i < len(extra_youtube_links) else ""
            notes = extra_notes[i].strip() if i < len(extra_notes) else ""

            if song_title:
                connection.execute("""
                    INSERT INTO ceremony_extra_songs
                    (song_title, artist_name, youtube_link, notes)
                    VALUES (?, ?, ?, ?)
                """, (song_title, artist_name, youtube_link, notes))

        vibe_preferences = connection.execute("SELECT * FROM vibe_preferences ORDER BY id ASC").fetchall()

        for vibe in vibe_preferences:
            vibe_id = vibe["id"]
            enabled = 1 if request.form.get(f"vibe_{vibe_id}") == "on" else 0

            connection.execute("""
                UPDATE vibe_preferences
                SET enabled = ?
                WHERE id = ?
            """, (enabled, vibe_id))

        must_song_titles = request.form.getlist("must_song_title[]")
        must_artist_names = request.form.getlist("must_artist_name[]")
        must_youtube_links = request.form.getlist("must_youtube_link[]")
        must_notes_list = request.form.getlist("must_notes[]")

        for i in range(len(must_song_titles)):
            song_title = must_song_titles[i].strip()

            artist_name = must_artist_names[i].strip() if i < len(must_artist_names) else ""
            youtube_link = must_youtube_links[i].strip() if i < len(must_youtube_links) else ""
            notes = must_notes_list[i].strip() if i < len(must_notes_list) else ""

            if song_title:
                connection.execute("""
                    INSERT INTO must_play
                    (song_title, artist_name, youtube_link, notes)
                    VALUES (?, ?, ?, ?)
                """, (song_title, artist_name, youtube_link, notes))

        no_song_titles = request.form.getlist("no_song_title[]")
        no_artist_names = request.form.getlist("no_artist_name[]")
        no_youtube_links = request.form.getlist("no_youtube_link[]")
        no_notes_list = request.form.getlist("no_notes[]")

        for i in range(len(no_song_titles)):
            song_title = no_song_titles[i].strip()

            artist_name = no_artist_names[i].strip() if i < len(no_artist_names) else ""
            youtube_link = no_youtube_links[i].strip() if i < len(no_youtube_links) else ""
            notes = no_notes_list[i].strip() if i < len(no_notes_list) else ""

            if song_title:
                connection.execute("""
                    INSERT INTO do_not_play
                    (song_title, artist_name, youtube_link, notes)
                    VALUES (?, ?, ?, ?)
                """, (song_title, artist_name, youtube_link, notes))

        connection.commit()
        connection.close()

        flash("Wedding music details updated successfully.")
        return redirect("/couple")

    (
        ceremony_formalities,
        reception_formalities,
        ceremony_extra_songs,
        must_play,
        do_not_play,
        vibe_preferences
    ) = get_formalities_data()

    return render_template(
        "couple.html",
        settings=settings,
        portal_locked=portal_locked,
        ceremony_formalities=ceremony_formalities,
        reception_formalities=reception_formalities,
        ceremony_extra_songs=ceremony_extra_songs,
        must_play=must_play,
        do_not_play=do_not_play,
        vibe_preferences=vibe_preferences
    )


@app.route("/admin")
@admin_required
def admin():
    settings = get_wedding_settings()

    connection = get_db_connection()

    predrinks_requests = connection.execute("""
        SELECT *
        FROM predrinks_requests
        ORDER BY votes DESC, requested_at DESC
    """).fetchall()

    reception_requests = connection.execute("""
        SELECT *
        FROM reception_requests
        ORDER BY requested_at DESC
    """).fetchall()

    connection.close()

    return render_template(
        "admin.html",
        predrinks_requests=predrinks_requests,
        reception_requests=reception_requests,
        settings=settings
    )


@app.route("/admin/formalities")
@admin_required
def admin_formalities():
    settings = get_wedding_settings()

    (
        ceremony_formalities,
        reception_formalities,
        ceremony_extra_songs,
        must_play,
        do_not_play,
        vibe_preferences
    ) = get_formalities_data()

    return render_template(
        "admin_formalities.html",
        settings=settings,
        ceremony_formalities=ceremony_formalities,
        reception_formalities=reception_formalities,
        ceremony_extra_songs=ceremony_extra_songs,
        must_play=must_play,
        do_not_play=do_not_play,
        vibe_preferences=vibe_preferences
    )


@app.route("/update-prep-status", methods=["POST"])
@admin_required
def update_prep_status():
    data = request.json

    table = data.get("table")
    row_id = data.get("id")
    status = data.get("status")

    allowed_tables = ["formalities", "ceremony_extra_songs", "must_play"]

    if table not in allowed_tables:
        return jsonify({"success": False})

    connection = get_db_connection()

    connection.execute(f"""
        UPDATE {table}
        SET prep_status = ?
        WHERE id = ?
    """, (status, row_id))

    connection.commit()
    connection.close()

    return jsonify({"success": True})


@app.route("/connect-spotify")
def connect_spotify():
    spotify_oauth = create_spotify_oauth()
    auth_url = spotify_oauth.get_authorize_url()
    return redirect(auth_url)


@app.route("/callback")
def callback():
    spotify_oauth = create_spotify_oauth()
    code = request.args.get("code")

    if not code:
        flash("Spotify connection failed.")
        return redirect("/predrinks")

    token_info = spotify_oauth.get_access_token(code, as_dict=True)

    session["spotify_token_info"] = token_info

    flash("Spotify connected successfully.")
    return redirect("/predrinks")


@app.route("/now-playing")
def now_playing_api():
    sp = get_logged_in_spotify()

    if not sp:
        return jsonify({"connected": False, "now_playing": None})

    now_playing = get_now_playing(sp)

    return jsonify({"connected": True, "now_playing": now_playing})


@app.route("/live-activity")
def live_activity_api():
    recent_activity = get_recent_activity()

    return jsonify([
        {
            "guest_name": row["guest_name"],
            "song_title": row["song_title"],
            "artist_name": row["artist_name"],
            "action": row["action"],
            "created_at": row["created_at"]
        }
        for row in recent_activity
    ])


@app.route("/predrinks", methods=["GET", "POST"])
def predrinks():
    spotify_results = []
    sp = get_logged_in_spotify()
    now_playing = get_now_playing(sp) if sp else None
    top_requested = get_top_requested()
    recent_activity = get_recent_activity()
    settings = get_wedding_settings()

    if request.method == "POST":
        if not sp:
            flash("Please connect Spotify first.")
            return redirect("/predrinks")

        if "search" in request.form:
            search_query = request.form["search_query"]

            results = sp.search(
                q=search_query,
                type="track",
                limit=10
            )

            spotify_results = results["tracks"]["items"]

            return render_template(
                "predrinks.html",
                spotify_results=spotify_results,
                spotify_connected=True,
                top_requested=top_requested,
                recent_activity=recent_activity,
                now_playing=now_playing,
                settings=settings
            )

        if "add_song" in request.form:
            guest_name = request.form["guest_name"]
            song_title = request.form["song_title"]
            artist_name = request.form["artist_name"]
            track_uri = request.form["track_uri"]

            connection = get_db_connection()

            existing_song = connection.execute("""
                SELECT *
                FROM predrinks_requests
                WHERE track_uri = ?
            """, (track_uri,)).fetchone()

            if existing_song:
                connection.execute("""
                    UPDATE predrinks_requests
                    SET votes = ?
                    WHERE track_uri = ?
                """, (existing_song["votes"] + 1, track_uri))

                connection.commit()
                connection.close()

                log_activity(guest_name, song_title, artist_name, "voted for")

                flash(f"{song_title} already exists. Vote added!")
                return redirect("/predrinks")

            sp.playlist_add_items(PLAYLIST_ID, [track_uri])

            connection.execute("""
                INSERT INTO predrinks_requests
                (guest_name, song_title, artist_name, track_uri, votes)
                VALUES (?, ?, ?, ?, ?)
            """, (guest_name, song_title, artist_name, track_uri, 1))

            connection.commit()
            connection.close()

            log_activity(guest_name, song_title, artist_name, "added")

            flash("Song added to Spotify playlist!")
            return redirect("/predrinks")

    return render_template(
        "predrinks.html",
        spotify_results=spotify_results,
        spotify_connected=sp is not None,
        top_requested=top_requested,
        recent_activity=recent_activity,
        now_playing=now_playing,
        settings=settings
    )


@app.route("/reception", methods=["GET", "POST"])
def reception():
    settings = get_wedding_settings()

    if request.method == "POST":
        guest_name = request.form["guest_name"]
        song_title = request.form["song_title"]
        artist_name = request.form["artist_name"]

        connection = get_db_connection()

        connection.execute("""
            INSERT INTO reception_requests
            (guest_name, song_title, artist_name, status)
            VALUES (?, ?, ?, ?)
        """, (guest_name, song_title, artist_name, "pending"))

        connection.commit()
        connection.close()

        flash("Request sent to DJ.")
        return redirect("/reception")

    return render_template("reception.html", settings=settings)


@app.route("/approve/<int:request_id>")
@admin_required
def approve_request(request_id):
    connection = get_db_connection()

    connection.execute("""
        UPDATE reception_requests
        SET status = ?
        WHERE id = ?
    """, ("approved", request_id))

    connection.commit()
    connection.close()

    return redirect("/admin")


@app.route("/reject/<int:request_id>")
@admin_required
def reject_request(request_id):
    connection = get_db_connection()

    connection.execute("""
        UPDATE reception_requests
        SET status = ?
        WHERE id = ?
    """, ("rejected", request_id))

    connection.commit()
    connection.close()

    return redirect("/admin")


@app.route("/played/<int:request_id>")
@admin_required
def played_request(request_id):
    connection = get_db_connection()

    connection.execute("""
        UPDATE reception_requests
        SET status = ?
        WHERE id = ?
    """, ("played", request_id))

    connection.commit()
    connection.close()

    return redirect("/admin")


@app.route("/delete-must-play/<int:song_id>")
def delete_must_play(song_id):
    connection = get_db_connection()

    connection.execute("DELETE FROM must_play WHERE id = ?", (song_id,))

    connection.commit()
    connection.close()

    flash("Must-play song removed.")
    return redirect("/couple")


@app.route("/delete-do-not-play/<int:song_id>")
def delete_do_not_play(song_id):
    connection = get_db_connection()

    connection.execute("DELETE FROM do_not_play WHERE id = ?", (song_id,))

    connection.commit()
    connection.close()

    flash("Do-not-play song removed.")
    return redirect("/couple")


@app.route("/qr")
def qr_page():
    qr_image = generate_qr_code()
    settings = get_wedding_settings()

    return render_template(
        "qr.html",
        qr_image=qr_image,
        settings=settings
    )


if __name__ == "__main__":
    app.run(debug=True)