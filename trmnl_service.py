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

    # Load custom fonts
    font_blockkie_title = ImageFont.truetype(os.path.join(FONTS_DIR, "BlockKie.ttf"), 36)
    font_blockkie_num = ImageFont.truetype(os.path.join(FONTS_DIR, "BlockKie.ttf"), 58)
    font_box_label = ImageFont.truetype(os.path.join(FONTS_DIR, "Inter_18pt-Regular.ttf"), 20)
    font_unit = ImageFont.truetype(os.path.join(FONTS_DIR, "Inter_18pt-Regular.ttf"), 28)
    font_unit_long = ImageFont.truetype(os.path.join(FONTS_DIR, "Inter_18pt-Regular.ttf"), 21)
    font_geneva_footer = ImageFont.truetype(os.path.join(FONTS_DIR, "geneva-9.ttf"), 14)
    font_inter_time = ImageFont.truetype(os.path.join(FONTS_DIR, "Inter_18pt-Regular.ttf"), 20)

    pad = 24

    # 1. Header
    # Circle indicator icon
    draw.ellipse([pad, pad, pad + 28, pad + 28], fill=0)
    draw.ellipse([pad + 7, pad + 7, pad + 21, pad + 21], fill=255)

    # Title
    title_str = str(data.get("title", "DAILY SOLAR STATUS")).upper()
    draw.text((pad + 38, pad - 4), title_str, fill=0, font=font_blockkie_title)

    # Last Updated Time (right aligned)
    time_str = data.get("last_updated", "")
    time_bbox = draw.textbbox((0, 0), time_str, font=font_inter_time)
    time_w = time_bbox[2] - time_bbox[0]
    time_h = time_bbox[3] - time_bbox[1]
    time_y = pad + (36 - time_h) // 2
    draw.text((WIDTH - pad - time_w, time_y), time_str, fill=0, font=font_inter_time)

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
        {"label": "TODAY'S SOLAR", "num": f"{data.get('production', 0.0):.1f}", "unit": "kWh"},
        {"label": "TODAY'S USAGE", "num": f"{data.get('consumption', 0.0):.1f}", "unit": "kWh"},
        {"label": "TODAY'S NET GRID", "num": data.get("net_grid_str", "+0.0"), "unit": data.get("net_grid_unit", "kWh Export")},
        {"label": "TODAY'S EXPORT", "num": f"{data.get('export', 0.0):.1f}", "unit": "kWh"},
        {"label": "TODAY'S IMPORT", "num": f"{data.get('import', 0.0):.1f}", "unit": "kWh"},
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

        num_bbox = draw.textbbox((0, 0), num_str, font=font_blockkie_num)
        num_w = num_bbox[2] - num_bbox[0]

        num_y = by2 - 68
        draw.text((bx + 14, num_y), num_str, fill=0, font=font_blockkie_num)

        if unit_str:
            u_font = font_unit_long if len(unit_str) > 5 else font_unit
            unit_baseline_offset = 21 if len(unit_str) > 5 else 28
            unit_y = (num_y + 52) - unit_baseline_offset
            draw.text((bx + 14 + num_w + 8, unit_y), unit_str, fill=0, font=u_font)



    # 3. Footer Bar
    footer_y = HEIGHT - pad - 26
    draw.rounded_rectangle([pad, footer_y, WIDTH - pad, footer_y + 28], radius=6, fill=0)
    draw.text((pad + 12, footer_y + 7), "ENPHASE DASHBOARD HISTORY INTEGRATION", fill=255, font=font_geneva_footer)

    # Active indicator
    active_str = "ACTIVE"
    draw.ellipse([WIDTH - pad - 72, footer_y + 10, WIDTH - pad - 64, footer_y + 18], fill=255)
    draw.text((WIDTH - pad - 58, footer_y + 7), active_str, fill=255, font=font_geneva_footer)

    # Convert to 1-bit monochrome image
    monochrome_img = img.convert("1", dither=Image.Dither.FLOYDSTEINBERG)

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
