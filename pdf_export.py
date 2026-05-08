from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


def generate_formalities_pdf(
    output_path,
    settings,
    ceremony_formalities,
    reception_formalities,
    ceremony_extra_songs,
    must_play,
    do_not_play,
    vibe_preferences
):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#5e4732"),
        spaceAfter=14
    )

    heading_style = ParagraphStyle(
        "HeadingStyle",
        parent=styles["Heading2"],
        fontSize=15,
        textColor=colors.HexColor("#7c644d"),
        spaceBefore=18,
        spaceAfter=8
    )

    normal_style = ParagraphStyle(
        "NormalStyle",
        parent=styles["BodyText"],
        fontSize=9,
        leading=12
    )

    story = []

    couple_names = settings["couple_names"] if settings else "Wedding"
    wedding_date = settings["wedding_date"] if settings else ""
    venue_name = settings["venue_name"] if settings else ""

    story.append(Paragraph(f"{couple_names}", title_style))
    story.append(Paragraph(f"{venue_name} | {wedding_date}", normal_style))
    story.append(Spacer(1, 16))
    story.append(Paragraph("Norky Wedding Music Preparation Sheet", heading_style))

    def clean(value):
        if value is None:
            return ""
        return str(value)

    def add_formality_section(title, rows):
        story.append(Paragraph(title, heading_style))

        data = [["Moment", "Song", "Artist", "YouTube", "Notes", "Status"]]

        for item in rows:
            if item["not_applicable"]:
                data.append([
                    clean(item["category"]),
                    "Not Applicable",
                    "",
                    "",
                    "",
                    ""
                ])
            else:
                data.append([
                    clean(item["category"]),
                    clean(item["song_title"]),
                    clean(item["artist_name"]),
                    "Yes" if clean(item["youtube_link"]) else "",
                    clean(item["notes"]),
                    clean(item["prep_status"]) if "prep_status" in item.keys() else ""
                ])

        table = Table(
            data,
            colWidths=[80, 90, 75, 45, 130, 70]
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c644d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8b9a6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f1ea")]),
        ]))

        story.append(table)
        story.append(Spacer(1, 12))

    def add_song_list(title, rows, include_status=False):
        story.append(Paragraph(title, heading_style))

        if include_status:
            data = [["Song", "Artist", "YouTube", "Notes", "Status"]]
        else:
            data = [["Song", "Artist", "YouTube", "Notes"]]

        if not rows:
            story.append(Paragraph("No songs submitted.", normal_style))
            story.append(Spacer(1, 10))
            return

        for song in rows:
            if include_status:
                data.append([
                    clean(song["song_title"]),
                    clean(song["artist_name"]),
                    "Yes" if clean(song["youtube_link"]) else "",
                    clean(song["notes"]),
                    clean(song["prep_status"]) if "prep_status" in song.keys() else ""
                ])
            else:
                data.append([
                    clean(song["song_title"]),
                    clean(song["artist_name"]),
                    "Yes" if clean(song["youtube_link"]) else "",
                    clean(song["notes"])
                ])

        col_widths = [110, 90, 50, 190, 70] if include_status else [120, 100, 60, 220]

        table = Table(data, colWidths=col_widths)

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c644d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8b9a6")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f1ea")]),
        ]))

        story.append(table)
        story.append(Spacer(1, 12))

    add_formality_section("Ceremony Music", ceremony_formalities)
    add_song_list("Additional Ceremony Songs", ceremony_extra_songs, include_status=True)
    add_formality_section("Reception Formalities", reception_formalities)

    story.append(Paragraph("Reception Vibes", heading_style))

    enabled_vibes = [
        vibe["preference_name"]
        for vibe in vibe_preferences
        if vibe["enabled"]
    ]

    if enabled_vibes:
        story.append(Paragraph(", ".join(enabled_vibes), normal_style))
    else:
        story.append(Paragraph("No reception vibe preferences selected.", normal_style))

    story.append(Spacer(1, 12))

    add_song_list("Must-Play Songs", must_play, include_status=True)
    add_song_list("Do-Not-Play Songs", do_not_play, include_status=False)

    story.append(Spacer(1, 16))
    story.append(Paragraph("Generated by Norky Wedding Media & Mobile DJ", normal_style))

    doc.build(story)