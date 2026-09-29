import os
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
from db import DailyStats

WIDTH = 800
HEIGHT = 480
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONTS_DIR = os.path.join(BASE_DIR, 'static', 'fonts')
OUTPUT_IMAGE_PATH = os.path.join(BASE_DIR, 'static', 'trmnl_display.png')
OUTPUT_BMP_PATH = os.path.join(BASE_DIR, 'static', 'trmnl_display.bmp')


def get_trmnl_data(app):
    """Fetch the latest daily solar stats and prepare formatting for TRMNL rendering."""
    from app import load_config
    from dashboard_services import get_target_timezone

    config = load_config()
    trmnl_config = config.get('trmnl', {})
    title = trmnl_config.get('title', 'DAILY SOLAR STATUS')

    tz = get_target_timezone()
    now_local = datetime.now(timezone.utc).astimezone(tz)
    last_updated_str = now_local.strftime('%b %d, %I:%M %p')

    with app.app_context():
        stats = DailyStats.query.order_by(DailyStats.date.desc()).first()

        if stats:
            production = stats.production_kwh or 0.0
            consumption = stats.consumption_kwh or 0.0
            export_val = stats.export_kwh or 0.0
            import_val = stats.import_kwh or 0.0
        else:
            production = 0.0
            consumption = 0.0
            export_val = 0.0
            import_val = 0.0

        net_grid = export_val - import_val
        direct_use = max(0.0, production - export_val)
        coverage = (direct_use / consumption * 100.0) if consumption > 0 else 0.0

        is_export = net_grid >= 0
        if is_export:
            net_grid_str = f"+{net_grid:.1f}"
            net_grid_unit = "kWh Export"
        else:
            net_grid_str = f"-{abs(net_grid):.1f}"
            net_grid_unit = "kWh"

        return {
            "title": title,
            "production": production,
            "consumption": consumption,
            "export": export_val,
            "import": import_val,
            "net_grid_str": net_grid_str,
            "net_grid_unit": net_grid_unit,
            "is_export": is_export,
            "coverage": coverage,
            "last_updated": last_updated_str
        }


def render_trmnl_solar(data: dict, output_png_path: str = OUTPUT_IMAGE_PATH, output_bmp_path: str = OUTPUT_BMP_PATH):
    """Renders 800x480 monochrome image matching the Daily Solar Status TRMNL recipe."""
    img = Image.new("L", (WIDTH, HEIGHT), color=255)
    draw = ImageDraw.Draw(img)

    # Load single consolidated font
    FONT_FILE = os.path.join(FONTS_DIR, "MonaspaceKrypton-SemiBold.otf")
    font_title = ImageFont.truetype(FONT_FILE, 25)
    font_time = ImageFont.truetype(FONT_FILE, 15)
    font_box_label = ImageFont.truetype(FONT_FILE, 15)
    font_num = ImageFont.truetype(FONT_FILE, 48)
    font_num_sm = ImageFont.truetype(FONT_FILE, 36)
    font_unit = ImageFont.truetype(FONT_FILE, 18)
    font_unit_long = ImageFont.truetype(FONT_FILE, 13)
    font_footer = ImageFont.truetype(FONT_FILE, 14)

    pad = 24

    # 1. Header
    # Circle indicator icon
    draw.ellipse([pad, pad, pad + 28, pad + 28], fill=0)
    draw.ellipse([pad + 7, pad + 7, pad + 21, pad + 21], fill=255)

    # Title
    title_str = str(data.get("title", "DAILY SOLAR STATUS")).upper()
    t_bbox = draw.textbbox((0, 0), title_str, font=font_title)
    t_h = t_bbox[3] - t_bbox[1]
    draw.text((pad + 38, pad + (28 - t_h) // 2 - t_bbox[1]), title_str, fill=0, font=font_title)

    # Last Updated Time (right aligned)
    time_str = data.get("last_updated", "")
    time_bbox = draw.textbbox((0, 0), time_str, font=font_time)
    time_w = time_bbox[2] - time_bbox[0]
    time_h = time_bbox[3] - time_bbox[1]
    time_y = pad + (28 - time_h) // 2 - time_bbox[1]
    draw.text((WIDTH - pad - time_w, time_y), time_str, fill=0, font=font_time)

    # Header divider line (4px black line)
    header_line_y = pad + 40
    draw.rectangle([pad, header_line_y, WIDTH - pad, header_line_y + 3], fill=0)

    # 2. 6-Box Grid (2 rows x 3 columns)
    grid_y = header_line_y + 16
    grid_h = 330
    cols = 3
    rows = 2
    gap_x = 16
    gap_y = 14

    col_w = (WIDTH - (2 * pad) - (gap_x * (cols - 1))) // cols
    row_h = (grid_h - (gap_y * (rows - 1))) // rows

    stats = [
        {"label": "SOLAR", "num": f"{data.get('production', 0.0):.1f}", "unit": "kWh"},
        {"label": "USAGE", "num": f"{data.get('consumption', 0.0):.1f}", "unit": "kWh"},
        {"label": "NET GRID", "num": data.get("net_grid_str", "+0.0"), "unit": data.get("net_grid_unit", "kWh Export")},
        {"label": "EXPORT", "num": f"{data.get('export', 0.0):.1f}", "unit": "kWh"},
        {"label": "IMPORT", "num": f"{data.get('import', 0.0):.1f}", "unit": "kWh"},
        {"label": "SOLAR COVERAGE", "num": f"{data.get('coverage', 0.0):.0f}", "unit": "%"},
    ]

    for idx, stat in enumerate(stats):
        r = idx // cols
        c = idx % cols
        bx = pad + c * (col_w + gap_x)
        by = grid_y + r * (row_h + gap_y)
        bx2 = bx + col_w
        by2 = by + row_h

        # Clean white card background with black border for all boxes
        draw.rounded_rectangle([bx, by, bx2, by2], radius=10, fill=255, outline=0, width=2)

        # Top-left text inside box
        draw.text((bx + 14, by + 14), stat["label"], fill=0, font=font_box_label)

        # Value + Unit
        num_str = stat["num"]
        unit_str = stat["unit"]

        u_font = font_unit_long if len(unit_str) > 5 else font_unit
        u_bbox = draw.textbbox((0, 0), unit_str, font=u_font) if unit_str else (0, 0, 0, 0)
        u_w = (u_bbox[2] - u_bbox[0]) if unit_str else 0

        n_font = font_num
        n_bbox = draw.textbbox((0, 0), num_str, font=n_font)
        n_w = n_bbox[2] - n_bbox[0]

        # If combined width is tight for the card, use slightly smaller number size
        if unit_str and (14 + n_w + 6 + u_w > col_w - 18):
            n_font = font_num_sm
            n_bbox = draw.textbbox((0, 0), num_str, font=n_font)
            n_w = n_bbox[2] - n_bbox[0]

        num_y = by2 - 62
        draw.text((bx + 14, num_y), num_str, fill=0, font=n_font)

        if unit_str:
            unit_y = (num_y + n_bbox[3]) - u_bbox[3]
            draw.text((bx + 14 + n_w + 6, unit_y), unit_str, fill=0, font=u_font)



    # 3. Footer Bar
    bar_h = 30
    footer_y = HEIGHT - pad - bar_h
    draw.rounded_rectangle([pad, footer_y, WIDTH - pad, footer_y + bar_h], radius=6, fill=0)

    footer_text = "ENPHASE DASHBOARD"
    f_bbox = draw.textbbox((0, 0), footer_text, font=font_footer)
    f_h = f_bbox[3] - f_bbox[1]
    f_y = footer_y + (bar_h - f_h) // 2 - f_bbox[1]
    draw.text((pad + 14, f_y), footer_text, fill=255, font=font_footer)

    # Active indicator
    active_str = "ACTIVE"
    a_bbox = draw.textbbox((0, 0), active_str, font=font_footer)
    a_w = a_bbox[2] - a_bbox[0]

    circ_r = 4
    circ_x = WIDTH - pad - 14 - a_w - 12
    circ_y = footer_y + bar_h // 2
    draw.ellipse([circ_x - circ_r, circ_y - circ_r, circ_x + circ_r, circ_y + circ_r], fill=255)
    draw.text((WIDTH - pad - 14 - a_w, f_y), active_str, fill=255, font=font_footer)

    # Convert to 1-bit monochrome image (crisp pixel rendering without dither speckles)
    monochrome_img = img.convert("1", dither=Image.Dither.NONE)

    # Save PNG
    os.makedirs(os.path.dirname(output_png_path), exist_ok=True)
    monochrome_img.save(output_png_path, format="PNG")

    # Save BMP
    if output_bmp_path:
        os.makedirs(os.path.dirname(output_bmp_path), exist_ok=True)
        monochrome_img.save(output_bmp_path, format="BMP")

    print(f"TRMNL solar screen rendered to {output_png_path}")
    return output_png_path


def update_trmnl_display(app):
    """Updates the rendered TRMNL display image with latest data."""
    try:
        data = get_trmnl_data(app)
        return render_trmnl_solar(data)
    except Exception as e:
        print(f"Error updating TRMNL display: {e}")
        return None
