#!/usr/bin/env python3
"""Generate clear text-based icons for PhotoFace watch face configuration.

Each icon is 200x200 RGBA PNG with white text on a dark circular background.
Icons use short, obvious labels so users can quickly identify each option.
"""

from PIL import Image, ImageDraw, ImageFont
import os

OUTPUT_DIR = "watchface/src/main/res/drawable"
SIZE = 200
BG_COLOR = (50, 50, 50, 255)       # Dark gray circle
TEXT_COLOR = (255, 255, 255, 255)   # White text
ACCENT_GREEN = (102, 187, 106, 255)
ACCENT_ORANGE = (255, 167, 38, 255)
ACCENT_RED = (239, 83, 80, 255)
ACCENT_BLUE = (79, 195, 247, 255)
ACCENT_YELLOW = (255, 238, 88, 255)
ACCENT_CYAN = (0, 229, 255, 255)

def find_font(size):
    """Find a suitable font."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()

def make_icon(filename, lines, font_size=None, line_colors=None):
    """Create a circular icon with centered text lines."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw filled dark circle
    draw.ellipse([4, 4, SIZE-5, SIZE-5], fill=BG_COLOR)

    # Auto-size font based on number of lines and text length
    if font_size is None:
        max_len = max(len(l) for l in lines)
        if len(lines) == 1:
            font_size = min(72, int(150 / max(max_len, 1)))
        elif len(lines) == 2:
            font_size = min(48, int(140 / max(max_len, 1)))
        else:
            font_size = min(36, int(130 / max(max_len, 1)))

    font = find_font(font_size)

    # Calculate total text height
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_heights.append(bbox[3] - bbox[1])
        line_widths.append(bbox[2] - bbox[0])

    spacing = 6
    total_h = sum(line_heights) + spacing * (len(lines) - 1)
    y = (SIZE - total_h) / 2

    for i, line in enumerate(lines):
        color = TEXT_COLOR
        if line_colors and i < len(line_colors):
            color = line_colors[i]
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (SIZE - w) / 2
        draw.text((x, y), line, fill=color, font=font)
        y += line_heights[i] + spacing

    img.save(os.path.join(OUTPUT_DIR, filename))
    print(f"  {filename}")


def make_bar_icon(filename, bars_data):
    """Create icon with colored horizontal bars and numbers (for HR zones)."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, SIZE-5, SIZE-5], fill=BG_COLOR)

    font = find_font(28)
    bar_h = 30
    gap = 10
    total = len(bars_data) * bar_h + (len(bars_data) - 1) * gap
    y = (SIZE - total) / 2

    for color, label in bars_data:
        # Bar
        bar_w = 70
        x_bar = 35
        draw.rounded_rectangle([x_bar, y, x_bar + bar_w, y + bar_h],
                               radius=4, fill=color)
        # Label
        bbox = draw.textbbox((0, 0), label, font=font)
        lw = bbox[2] - bbox[0]
        draw.text((x_bar + bar_w + 12, y + 1), label, fill=TEXT_COLOR, font=font)
        y += bar_h + gap

    img.save(os.path.join(OUTPUT_DIR, filename))
    print(f"  {filename}")


def make_arc_icon(filename, thickness):
    """Create icon showing arc thickness."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, SIZE-5, SIZE-5], fill=BG_COLOR)

    # Draw a partial arc to show thickness
    pad = 30
    draw.arc([pad, pad, SIZE-pad, SIZE-pad], start=200, end=340,
             fill=ACCENT_BLUE, width=thickness)

    img.save(os.path.join(OUTPUT_DIR, filename))
    print(f"  {filename}")


def make_markers_icon(filename, count):
    """Create icon showing hour markers."""
    import math
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, SIZE-5, SIZE-5], fill=BG_COLOR)

    if count == 0:
        font = find_font(48)
        text = "NONE"
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        draw.text(((SIZE-w)/2, (SIZE-h)/2), text, fill=TEXT_COLOR, font=font)
    else:
        # Draw tick marks around the circle
        cx, cy = SIZE/2, SIZE/2
        r_outer = 88
        r_inner = 70
        angles = []
        if count == 4:
            angles = [0, 90, 180, 270]
        else:  # 12
            angles = [i * 30 for i in range(12)]

        for angle_deg in angles:
            angle = math.radians(angle_deg - 90)
            x1 = cx + r_inner * math.cos(angle)
            y1 = cy + r_inner * math.sin(angle)
            x2 = cx + r_outer * math.cos(angle)
            y2 = cy + r_outer * math.sin(angle)
            draw.line([(x1, y1), (x2, y2)], fill=TEXT_COLOR, width=4)

    img.save(os.path.join(OUTPUT_DIR, filename))
    print(f"  {filename}")


def make_hand_icon(filename, style_label):
    """Create icon showing hand style name."""
    make_icon(filename, [style_label], font_size=32)


print("Generating PhotoFace config icons...")
print()

# === PARALLAX STRENGTH ===
print("Parallax Strength:")
make_icon("ic_parallax_off.png", ["OFF"], font_size=56)
make_icon("ic_parallax_subtle.png", ["SUBTLE"], font_size=36)
make_icon("ic_parallax_medium.png", ["MED"], font_size=52)
make_icon("ic_parallax_strong.png", ["STRONG"], font_size=32)

# === PHOTO TINT ===
print("Photo Tint:")
make_icon("ic_tint_none.png", ["NONE"], font_size=48)
make_icon("ic_tint_light.png", ["LIGHT"], font_size=40)
make_icon("ic_tint_medium.png", ["MED"], font_size=52)
make_icon("ic_tint_heavy.png", ["HEAVY"], font_size=36)

# === HAND STYLE ===
print("Hand Style:")
make_hand_icon("ic_hand_classic.png", "CLASSIC")
make_hand_icon("ic_hand_tapered.png", "TAPER")
make_hand_icon("ic_hand_dauphine.png", "DAUPH")
make_hand_icon("ic_hand_block.png", "BLOCK")

# === SECOND HAND ===
print("Second Hand:")
make_icon("ic_second_off.png", ["SEC", "OFF"], font_size=40)
make_icon("ic_second_on.png", ["SEC", "ON"], font_size=40, line_colors=[TEXT_COLOR, ACCENT_GREEN])

# === HOUR MARKERS ===
print("Hour Markers:")
make_markers_icon("ic_markers_none.png", 0)
make_markers_icon("ic_markers_four.png", 4)
make_markers_icon("ic_markers_twelve.png", 12)

# === QUADRANT WIDGETS ===
print("Widgets:")
make_icon("ic_widget_battery.png", ["BAT"], font_size=52, line_colors=[ACCENT_GREEN])
make_icon("ic_widget_steps.png", ["STEP"], font_size=44, line_colors=[ACCENT_BLUE])
make_icon("ic_widget_heart.png", ["HR"], font_size=56, line_colors=[ACCENT_RED])
make_icon("ic_widget_date.png", ["DATE"], font_size=44, line_colors=[ACCENT_ORANGE])
make_icon("ic_widget_floors.png", ["FLR"], font_size=52, line_colors=[ACCENT_CYAN])
make_icon("ic_widget_none.png", ["NONE"], font_size=48)

# === ARC THICKNESS ===
print("Arc Thickness:")
make_arc_icon("ic_arc_thin.png", 4)
make_arc_icon("ic_arc_medium.png", 10)
make_arc_icon("ic_arc_thick.png", 18)

# === HEART RATE ZONES ===
print("Heart Rate Zones:")
make_icon("ic_zone_off.png", ["ZONE", "OFF"], font_size=40)
make_bar_icon("ic_zone_relaxed.png", [
    (ACCENT_GREEN, "80"),
    (ACCENT_YELLOW, "120"),
    (ACCENT_ORANGE, "150"),
])
make_bar_icon("ic_zone_standard.png", [
    (ACCENT_GREEN, "70"),
    (ACCENT_YELLOW, "100"),
    (ACCENT_ORANGE, "130"),
])
make_bar_icon("ic_zone_athletic.png", [
    (ACCENT_GREEN, "60"),
    (ACCENT_YELLOW, "85"),
    (ACCENT_ORANGE, "110"),
])

# === LABEL SIZE ===
print("Label Size:")
make_icon("ic_label_small.png", ["Sm"], font_size=36)
make_icon("ic_label_medium.png", ["Md"], font_size=48)
make_icon("ic_label_large.png", ["Lg"], font_size=60)
make_icon("ic_label_xlarge.png", ["XL"], font_size=72)

# === TAP ACTIONS ===
print("Tap Actions:")
make_icon("ic_tap_none.png", ["NONE"], font_size=48)
make_icon("ic_tap_battery.png", ["BAT"], font_size=52, line_colors=[ACCENT_GREEN])
make_icon("ic_tap_health.png", ["HEALTH"], font_size=32, line_colors=[ACCENT_RED])
make_icon("ic_tap_calendar.png", ["CAL"], font_size=52, line_colors=[ACCENT_BLUE])
make_icon("ic_tap_settings.png", ["SET"], font_size=52)
make_icon("ic_tap_phone.png", ["PHONE"], font_size=34)
make_icon("ic_tap_messages.png", ["MSG"], font_size=52)
make_icon("ic_tap_music.png", ["MUSIC"], font_size=36, line_colors=[ACCENT_ORANGE])
make_icon("ic_tap_alarm.png", ["ALARM"], font_size=34, line_colors=[ACCENT_YELLOW])

# === WORLD CLOCK / TIMEZONE ===
print("World Clock / Timezone:")
make_icon("ic_world_clock.png", ["WORLD", "CLOCK"], font_size=32)
make_icon("ic_tz_off.png", ["OFF"], font_size=56)
make_icon("ic_tz_london.png", ["LON"], font_size=48)
make_icon("ic_tz_paris.png", ["PAR"], font_size=48)
make_icon("ic_tz_berlin.png", ["BER"], font_size=48)
make_icon("ic_tz_moscow.png", ["MOW"], font_size=48)
make_icon("ic_tz_dubai.png", ["DXB"], font_size=48)
make_icon("ic_tz_mumbai.png", ["BOM"], font_size=48)
make_icon("ic_tz_singapore.png", ["SIN"], font_size=48)
make_icon("ic_tz_hong_kong.png", ["HKG"], font_size=48)
make_icon("ic_tz_tokyo.png", ["TYO"], font_size=48)
make_icon("ic_tz_sydney.png", ["SYD"], font_size=48)
make_icon("ic_tz_los_angeles.png", ["LAX"], font_size=48)
make_icon("ic_tz_denver.png", ["DEN"], font_size=48)
make_icon("ic_tz_chicago.png", ["CHI"], font_size=48)
make_icon("ic_tz_new_york.png", ["NYC"], font_size=48)
make_icon("ic_tz_sao_paulo.png", ["GRU"], font_size=48)
make_icon("ic_tz_madrid.png", ["MAD"], font_size=48)

# === COLOR SWATCHES (keep as solid color circles) ===
print("Color Swatches:")
color_map = {
    "green": (102, 187, 106),
    "purple": (186, 104, 200),
    "orange": (255, 167, 38),
    "blue": (79, 195, 247),
    "red": (239, 83, 80),
    "cyan": (38, 198, 218),
    "yellow": (255, 238, 88),
    "pink": (236, 64, 122),
    "white": (255, 255, 255),
    "silver": (192, 192, 192),
    "gold": (255, 215, 0),
}
for name, rgb in color_map.items():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, SIZE-5, SIZE-5], fill=(*rgb, 255))
    fname = f"ic_color_{name}.png"
    img.save(os.path.join(OUTPUT_DIR, fname))
    print(f"  {fname}")

print()
print("Done! All icons generated.")
