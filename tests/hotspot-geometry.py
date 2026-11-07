"""Check the character targets against the PNG coordinate space without opening a window."""
import re
from pathlib import Path

from PIL import Image


root = Path(__file__).resolve().parents[1]
css = (root / "static/style.css").read_text()
image = Image.open(root / "static/artwork/soldier-navigation-v1.png")
assert image.size == (1024, 1536)
assert ".forge-screen .armor-board{container-type:size;" in css
assert ".forge-screen .soldier-artboard{position:relative;width:min(75cqw,66.667cqh);height:auto;" in css
assert "aspect-ratio:2/3" in css
assert ".forge-screen .soldier-artboard>img{width:100%;height:100%;object-fit:fill" in css

# These regions were checked against the native soldier image, separately from the CSS.
expected = {
    "helmet": ((.39, .61), (.03, .10)),
    "mask": ((.41, .59), (.11, .19)),
    "top": ((.36, .64), (.23, .40)),
    "gloves.hand-left": ((.17, .29), (.42, .56)),
    "gloves.hand-right": ((.71, .83), (.42, .56)),
    "bottoms.leg-left": ((.33, .48), (.53, .78)),
    "bottoms.leg-right": ((.52, .67), (.53, .78)),
    "shoes.foot-left": ((.25, .44), (.85, .97)),
    "shoes.foot-right": ((.56, .75), (.85, .97)),
}


def rule(name):
    selector = ".region-" + name
    match = re.search(re.escape(selector) + r"\{([^}]*)\}", css)
    assert match, selector
    return {key: float(value) / 100 for key, value in re.findall(r"(top|left|right|width|height):(\d+(?:\.\d+)?)(?:%|(?=;|\}))", match.group(1))}


for viewport, viewport_height in [(1280, 720), (1440, 900), (2596, 1296), (3440, 1350)]:
    screen = min(viewport, 2400)
    left_column = screen * (.51 if viewport <= 1350 else .52)
    workspace_height = viewport_height - 56 - 42
    stage_height = workspace_height - (92 if viewport_height <= 760 else 112)
    art_width = min(left_column * .75, stage_height * .66667)
    art_height = art_width * 1.5
    assert art_height <= stage_height + 0.01
    art_left = (left_column - art_width) / 2
    art_top = (stage_height - art_height) / 2
    bounds = {}
    for name, (x_expected, y_expected) in expected.items():
        item = rule(name)
        width, height = max(44, item["width"] * art_width), max(44, item["height"] * art_height)
        x = item.get("left", 1 - item.get("right", 0) - item["width"]) * art_width
        y = item["top"] * art_height
        cx, cy = (x + width / 2) / art_width, (y + height / 2) / art_height
        assert x_expected[0] <= cx <= x_expected[1], (viewport, name, cx)
        assert y_expected[0] <= cy <= y_expected[1], (viewport, name, cy)
        assert image.getpixel((round(cx * 1023), round(cy * 1535)))[3] > 200, (viewport, name, cx, cy)
        bounds[name] = (x, y, x + width, y + height, art_left + cx * art_width, art_top + cy * art_height)
    # Centers must remain usable as pointer targets even where generous boxes overlap.
    for name, (_, _, _, _, cx, cy) in bounds.items():
        local_x, local_y = cx - art_left, cy - art_top
        assert not any(other != name and a <= local_x <= c and b <= local_y <= d
                       for other, (a, b, c, d, _, _) in bounds.items()), (viewport, name)
        # Armor cards float over the stage; target centers still need a pointer path.
        for side in ("left", "right"):
            card_x = (.03 if side == "left" else .70) * left_column
            card_width = .27 * left_column
            card_top = .05 * stage_height
            card_area = (.71 if side == "left" else .86) * stage_height
            card_height = min(105, max(72, .10 * viewport_height))
            for row in range(3):
                card_center = card_top + (row + .5) * card_area / 3
                assert not (card_x <= cx <= card_x + card_width and
                            card_center - card_height / 2 <= cy <= card_center + card_height / 2), (viewport, name, side, row)
    print(f"{viewport}×{viewport_height} geometry: {art_width:.1f}×{art_height:.1f} artboard; target centers visible and aligned")
