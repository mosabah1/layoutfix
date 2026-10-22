# -*- coding: utf-8 -*-
"""
يولّد layoutfix.ico - حرف عربي وحرف لاتيني يتبادلان، مع سهم التبديل.
يحتاج Pillow، ويُشغَّل مرة واحدة عند تغيير التصميم:  python make_icon.py
"""
import os

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
BG = (37, 99, 235)          # ازرق
FG = (255, 255, 255)
ACCENT = (147, 197, 253)    # ازرق فاتح للسهم


def pick_font(size, names=("segoeui.ttf", "tahoma.ttf", "arial.ttf")):
    for name in names:
        path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                            "Fonts", name)
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default()


def centered(draw, xy, text, font, fill):
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text((xy[0] - (right + left) / 2, xy[1] - (bottom + top) / 2),
              text, font=font, fill=fill)


def build():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # خلفية مربعة بزوايا دائرية
    d.rounded_rectangle([8, 8, SIZE - 8, SIZE - 8], radius=52, fill=BG)

    big = pick_font(104)
    small = pick_font(58)

    centered(d, (SIZE * 0.34, SIZE * 0.36), "A", big, FG)      # لاتيني
    centered(d, (SIZE * 0.66, SIZE * 0.64), "ع", big, FG)      # عربي

    # سهم التبديل بين الحرفين
    d.line([(SIZE * 0.60, SIZE * 0.33), (SIZE * 0.80, SIZE * 0.33)],
           fill=ACCENT, width=12)
    d.polygon([(SIZE * 0.82, SIZE * 0.33), (SIZE * 0.72, SIZE * 0.26),
               (SIZE * 0.72, SIZE * 0.40)], fill=ACCENT)
    d.line([(SIZE * 0.20, SIZE * 0.67), (SIZE * 0.40, SIZE * 0.67)],
           fill=ACCENT, width=12)
    d.polygon([(SIZE * 0.18, SIZE * 0.67), (SIZE * 0.28, SIZE * 0.60),
               (SIZE * 0.28, SIZE * 0.74)], fill=ACCENT)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "layoutfix.ico")
    img.save(out, sizes=[(256, 256), (128, 128), (64, 64),
                         (48, 48), (32, 32), (16, 16)])
    print("كُتبت:", out)
    return out


if __name__ == "__main__":
    build()
