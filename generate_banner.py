"""テストバナー画像 (static/test-banner.jpg) を生成する

日本語字形で描画するため Noto Sans JP を使う。
ローカルに無い場合は Google Fonts から取得してキャッシュする。
実行: python generate_banner.py
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import urllib.request

FONT_URL = "https://github.com/notofonts/noto-cjk/raw/main/Sans/Variable/TTF/Subset/NotoSansJP-VF.ttf"
FONT_CACHE = Path.home() / ".cache" / "tobetsu-fonts" / "NotoSansJP-VF.ttf"


def ensure_font() -> Path:
    if not FONT_CACHE.exists():
        FONT_CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(FONT_URL, FONT_CACHE)
    return FONT_CACHE


def load_font(path: Path, size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(path), size)
    try:
        font.set_variation_by_name(weight)
    except Exception:
        pass
    return font


def generate_banner():
    width, height = 1040, 585
    bg_color = (0, 91, 172)
    text_color = (255, 255, 255)
    btn_color = (6, 199, 85)

    font_path = ensure_font()
    title_font = load_font(font_path, 76)
    sub_font = load_font(font_path, 40, "Medium")
    label_font = load_font(font_path, 38, "Medium")
    btn_font = load_font(font_path, 44)

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    draw.text((width // 2, 175), "当別町 ごみ収集ボット",
              font=title_font, fill=text_color, anchor="mm")
    draw.text((width // 2, 255), "毎日のごみ出し情報をLINEでお届け",
              font=sub_font, fill=text_color, anchor="mm")
    draw.text((width // 2, 325), "【 非公式 】",
              font=label_font, fill=text_color, anchor="mm")

    btn_text = "友だち追加で無料でご利用"
    bbox = draw.textbbox((0, 0), btn_text, font=btn_font)
    btn_w = bbox[2] - bbox[0] + 90
    btn_h = 100
    btn_x = (width - btn_w) // 2
    btn_y = height - 180
    draw.rounded_rectangle([btn_x, btn_y, btn_x + btn_w, btn_y + btn_h],
                           radius=50, fill=btn_color)
    draw.text((width // 2, btn_y + btn_h // 2), btn_text,
              font=btn_font, fill=(255, 255, 255), anchor="mm")

    output_path = "static/test-banner.jpg"
    img.save(output_path, "JPEG", quality=95)
    print(f"Generated: {output_path} (font: {font_path})")


if __name__ == "__main__":
    generate_banner()
