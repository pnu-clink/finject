"""Compact NS/AS examples with larger text, condensed from stored Figure4-a cases."""
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "paper/asset/figures"


def build_figure(output: Path = OUT) -> None:
    output.mkdir(parents=True, exist_ok=True)
    document = fitz.open()
    page = document.new_page(width=620, height=340)
    navy = (.12, .23, .29)
    blue = (.19, .36, .47)
    green = (.13, .39, .32)
    gray = (.37, .42, .45)
    fonts = {name: fitz.Font(name) for name in ("helv", "hebo")}

    def text(x, y, value, size=26, color=navy, bold=False, maxwidth=274):
        font = "hebo" if bold else "helv"
        if fonts[font].text_length(value, fontsize=size) > maxwidth:
            raise ValueError("Figure text exceeds its column: " + value)
        page.insert_text((x, y), value, fontsize=size, fontname=font, color=color)

    text(10, 32, "Change in diluted shares, 2012-2013?", 28, bold=True, maxwidth=600)
    text(10, 58, "2012: 328.4 million shares", 24, color=gray, maxwidth=600)
    for x, title, color in [(8, "NS  Numeric Ans.", blue), (318, "AS  Abstention", green)]:
        page.draw_rect(fitz.Rect(x, 70, x + 294, 337), color=color, width=1)
        page.draw_rect(fitz.Rect(x, 70, x + 294, 117), color=None,
                       fill=tuple(.91 + .09 * c for c in color))
        text(x + 10, 103, title, 28, color, True)
        text(x + 10, 136, "EVIDENCE", 20, color, True)
        text(x + 10, 217, "REASON", 20, color, True)
        page.draw_line((x + 10, 199), (x + 284, 199), color=(.83, .86, .87), width=.5)
        page.draw_line((x + 10, 279), (x + 284, 279), color=(.83, .86, .87), width=.5)
    for x, lines in [(18, ["2013 basic: 320.9", "Dilutive effect: 5.6"]),
                     (328, ["2013 table: 326.5", "Added claim: 359.15"])]:
        for y, value in zip([160, 188], lines):
            text(x, y, value)
    for x, lines in [(18, ["320.9 + 5.6 = 326.5", "326.5 - 328.4 = -1.9"]),
                     (328, ["No rule resolves", "the conflict."])]:
        for y, value in zip([245, 273], lines):
            text(x, y, value)
    text(18, 304, "Answer: -1.9", 28, blue, True)
    text(328, 304, "Answer: null", 28, green, True)
    text(18, 331, "FAV: Supported", 24, blue, True)
    text(328, 331, "ARV + FAV: Supported", 24, green, True)
    document.set_metadata({"title": "Examples of NS and AS responses",
                           "subject": "Condensed NS and AS examples from stored Figure4-a cases",
                           "author": "FInject"})
    document.save(output / "Figure4-a-supported.pdf", garbage=4, deflate=True)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pixmap.save(output / "Figure4-a-supported.png")
    (output / "preview").mkdir(exist_ok=True)
    pixmap.save(output / "preview/Figure4-a-supported.png")
    document.close()


if __name__ == "__main__":
    build_figure()
