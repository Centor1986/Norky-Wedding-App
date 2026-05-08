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
app.secret_key = "norky-secret-key"

PLAYLIST_ID = os.getenv("SPOTIFY_PREDRINKS_PLAYLIST_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "norky123")


# =========================
# HELPERS
# =========================

def get_db_connection():
    connection = sqlite3.connect("norky_wedding.db")
    connection.row_factory = sqlite3.Row
    return connection


def get_wedding_settings():
    connection = get_db_connection()

    settings = connection.execute(
        "SELECT * FROM wedding_settings WHERE id = 1"
    ).fetchone()

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

    date_text = date_text.strip()

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
                date_text,
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

    lock_date = wedding_date - timedelta(days=1)

    return date.today() >= lock_date


def get_logged_in_spotify():

    token_info = session.get(
        "spotify_token_info",
        None
    )

    if not token_info:
        return None

    return get_spotify_client_from_token(
        token_info
    )


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
            "album_art":
                track["album"]["images"][0]["url"]
                if track["album"]["images"]
                else "",
            "is_playing":
                current.get("is_playing", False)
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

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        data = response.json()

    except Exception:
        return []

    results = []

    for item in data.get("items", []):

        video_id = item["id"]["videoId"]

        results.append({
            "title": item["snippet"]["title"],
            "channel":
                item["snippet"]["channelTitle"],
            "thumbnail":
                item["snippet"]["thumbnails"]["medium"]["url"],
            "youtube_link":
                f"https://www.youtube.com/watch?v={video_id}"
        })

    return results


def get_top_requested():

    connection = get_db_connection()

    top_requested = connection.execute(
        """
        SELECT *
        FROM predrinks_requests
        ORDER BY votes DESC, requested_at DESC
        LIMIT 5
        """
    ).fetchall()

    connection.close()

    return top_requested


def get_recent_activity():

    connection = get_db_connection()

    recent_activity = connection.execute(
        """
        SELECT *
        FROM activity_log
        ORDER BY created_at DESC
        LIMIT 8
        """
    ).fetchall()

    connection.close()

    return recent_activity


def log_activity(
    guest_name,
    song_title,
    artist_name,
    action
):

    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO activity_log
        (
            guest_name,
            song_title,
            artist_name,
            action
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            guest_name,
            song_title,
            artist_name,
            action
        )
    )

    connection.commit()
    connection.close()


def get_formalities_data():

    connection = get_db_connection()

    ceremony_formalities = connection.execute(
        """
        SELECT *
        FROM formalities
        WHERE section = 'Ceremony'
        AND category != 'Guest Arrival'
        ORDER BY id ASC
        """
    ).fetchall()

    reception_formalities = connection.execute(
        """
        SELECT *
        FROM formalities
        WHERE section = 'Reception'
        ORDER BY id ASC
        """
    ).fetchall()

    ceremony_extra_songs = connection.execute(
        """
        SELECT *
        FROM ceremony_extra_songs
        ORDER BY id DESC
        """
    ).fetchall()

    must_play = connection.execute(
        """
        SELECT *
        FROM must_play
        ORDER BY id DESC
        """
    ).fetchall()

    do_not_play = connection.execute(
        """
        SELECT *
        FROM do_not_play
        ORDER BY id DESC
        """
    ).fetchall()

    vibe_preferences = connection.execute(
        """
        SELECT *
        FROM vibe_preferences
        ORDER BY id ASC
        """
    ).fetchall()

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

    qr_path = os.path.join(
        "static",
        "qr",
        "wedding_qr.png"
    )

    url = "http://127.0.0.1:5000/"

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

        else:

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

    return render_template(
        "landing.html",
        settings=settings
    )


@app.route("/youtube-search-api")
def youtube_search_api():

    query = request.args.get(
        "q",
        ""
    ).strip()

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

    pdf_path = os.path.join(
        "static",
        "formalities_export.pdf"
    )

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

    return send_file(
        pdf_path,
        as_attachment=True
    )


@app.route("/settings", methods=["GET", "POST"])
@admin_required
def wedding_settings():

    connection = get_db_connection()

    if request.method == "POST":

        connection.execute(
            """
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
            """,
            (
                request.form["couple_names"],
                request.form["wedding_date"],
                request.form["venue_name"],
                request.form["welcome_message"],
                request.form["facebook_link"],
                request.form["instagram_link"],
                request.form["tiktok_link"]
            )
        )

        connection.commit()

        flash(
            "Wedding settings updated successfully."
        )

    settings = connection.execute(
        """
        SELECT *
        FROM wedding_settings
        WHERE id = 1
        """
    ).fetchone()

    connection.close()

    return render_template(
        "settings.html",
        settings=settings
    )


@app.route("/couple")
def couple_portal():

    settings = get_wedding_settings()

    portal_locked = is_couple_portal_locked(
        settings
    )

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

    predrinks_requests = connection.execute(
        """
        SELECT *
        FROM predrinks_requests
        ORDER BY votes DESC, requested_at DESC
        """
    ).fetchall()

    reception_requests = connection.execute(
        """
        SELECT *
        FROM reception_requests
        ORDER BY requested_at DESC
        """
    ).fetchall()

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

    allowed_tables = [
        "formalities",
        "ceremony_extra_songs",
        "must_play"
    ]

    if table not in allowed_tables:
        return jsonify({"success": False})

    connection = get_db_connection()

    connection.execute(
        f"""
        UPDATE {table}
        SET prep_status = ?
        WHERE id = ?
        """,
        (
            status,
            row_id
        )
    )

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

        flash(
            "Spotify connection failed."
        )

        return redirect("/predrinks")

    token_info = spotify_oauth.get_access_token(
        code,
        as_dict=True
    )

    session["spotify_token_info"] = token_info

    flash(
        "Spotify connected successfully."
    )

    return redirect("/predrinks")


@app.route("/predrinks")
def predrinks():

    spotify_results = []

    sp = get_logged_in_spotify()

    now_playing = (
        get_now_playing(sp)
        if sp else None
    )

    top_requested = get_top_requested()

    recent_activity = get_recent_activity()

    settings = get_wedding_settings()

    return render_template(
        "predrinks.html",
        spotify_results=spotify_results,
        spotify_connected=sp is not None,
        top_requested=top_requested,
        recent_activity=recent_activity,
        now_playing=now_playing,
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