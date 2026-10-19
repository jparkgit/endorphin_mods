"""
Create a pixel-pet mod from a folder of keyed-background frame images, mirroring pixel-kitty.

Purpose:

- Key out the background, pixelate every frame at pixel-kitty's cell size, and write source SVGs.
- Copy pixel-kitty's mod files for the new pet, build its frames, and register it for /pet.

Special Notes:

- Run as python3 createpet.py <name> <image folder> [--display ..] [--kind ..] [--move ..]
  [--step ..] [--colors ..] [--seconds ..] [--height ..] [--key #rrggbb]. Run from anywhere; the repo is found from this file.
- Needs Pillow. Images are read in natural file name order (2 before 10).
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[4]
TEMPLATE = REPO / "pixel-kitty"

# pixel-kitty's grid is 42 cells tall, so one cell is the same size when the cat is scaled to it.
DEFAULT_HEIGHT = 42

# A pixel counts as background when the key channel beats the other two by this much (of 255).
# Measured on bright green: background ran 200+, a pink or tan cat stays well under 40.
KEY_DOMINANCE = 80

# A mixed edge pixel keeps this much opacity or more as a cell. Half is the neutral cut.
ALPHA_CUT = 128

# Few colors keep each frame small enough for one Svg and read as pixel art.
DEFAULT_COLORS = 24

# Files copied unchanged apart from the name swaps.
COPIED = ["hooks/register.tsx", "hooks/pets.ts", "hooks/hooks.json", "tests/pets.test.ts",
          "types/index.d.ts", "tsconfig.json", "tools/build_frames.py", "README.md"]

PET_LINE = re.compile(r"(  \{ mod: '[^']+', word: '[^']+', name: '[^']+' \},\n)(\] as const)")


def natural(path: Path) -> list:
    """Sort key that orders frame_2 before frame_10."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", path.name)]


def key_frame(image: Image.Image, key: tuple[int, int, int]) -> Image.Image:
    """
    Make the key color transparent and remove its tint from the edge pixels.

    Args:
        image: A frame on a solid key-colored background.
        key: The background color.

    Returns:
        The frame as RGBA, background transparent.
    """
    channel = max(range(3), key=lambda i: key[i])
    others = [i for i in range(3) if i != channel]
    pixels = image.convert("RGB").load()
    out = Image.new("RGBA", image.size)
    put = out.load()

    for y in range(image.height):
        for x in range(image.width):
            px = pixels[x, y]
            over = px[channel] - max(px[i] for i in others)

            if over >= KEY_DOMINANCE:
                continue

            if over > 0:
                px = tuple(max(px[i] for i in others) if i == channel else px[i] for i in range(3))

            put[x, y] = (*px, 255)

    return out


def pixelate(frames: list[Image.Image], height: int) -> list[list[list[str | None]]]:
    """
    Crop every frame to the box holding them all, then scale to height cells tall.

    Args:
        frames: RGBA frames of one size.
        height: Cells tall for the shared box.

    Returns:
        One row-major grid of hex colors per frame, None where transparent.

    Raises:
        ValueError: When every frame is empty.
    """
    boxes = [f.getchannel("A").getbbox() for f in frames]
    boxes = [b for b in boxes if b]

    if not boxes:
        raise ValueError("every frame is empty after keying out the background")

    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    width = max(1, round((box[2] - box[0]) * height / (box[3] - box[1])))
    grids = []

    for frame in frames:
        small = frame.crop(box).resize((width, height), Image.LANCZOS)
        px = small.load()
        grids.append([[None if px[x, y][3] < ALPHA_CUT else "#%02x%02x%02x" % px[x, y][:3]
                       for x in range(width)] for y in range(height)])

    return grids


def quantize(grids: list[list[list[str | None]]], colors: int) -> None:
    """Replace every cell color, in place, by the nearest of a shared palette of colors colors."""
    cells = sorted({c for g in grids for row in g for c in row if c})
    strip = Image.new("RGB", (len(cells), 1))
    strip.putdata([tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in cells])
    mapped = strip.quantize(colors, Image.MEDIANCUT).convert("RGB")
    lookup = {c: "#%02x%02x%02x" % mapped.getpixel((i, 0)) for i, c in enumerate(cells)}

    for g in grids:
        for row in g:
            row[:] = [lookup[c] if c else None for c in row]


def source_svg(grid: list[list[str | None]]) -> str:
    """Write a grid as the rect-per-run SVG that build_frames.py reads."""
    rects = []

    for y, row in enumerate(grid):
        x = 0

        while x < len(row):
            if row[x] is None:
                x += 1
                continue

            start = x

            while x < len(row) and row[x] == row[start]:
                x += 1

            rects.append(f'<rect x="{start}" y="{y}" width="{x - start}" height="1" fill="{row[start]}"/>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{len(grid[0]) * 10}" height="{len(grid) * 10}" '
            f'viewBox="0 0 {len(grid[0])} {len(grid)}" shape-rendering="crispEdges">{"".join(rects)}</svg>')


def swap(text: str, a: argparse.Namespace) -> str:
    """Rename pixel-kitty's wording and identifiers to the new pet's."""
    word = a.name
    for old, new in [("dance side by side", a.summary), ("two dancing pixel kittens", a.kind),
                     ("The kittens", a.display[:1].upper() + a.display[1:]), ("the kittens", a.display),
                     ("pixel-kitty", word), ("KITTY_", f"{word.upper()}_"), ("/pet kitty", f"/pet {word}")]:
        text = text.replace(old, new)
    return text


def register(a: argparse.Namespace, mods: list[Path]) -> None:
    """Add the pet to the PETS list in every mod, and the /pet line to every README."""
    entry = f"  {{ mod: '{a.name}', word: '{a.name}', name: '{a.display}' }},\n"

    for mod in mods:
        pets = mod / "hooks" / "pets.ts"
        text = pets.read_text()

        if f"mod: '{a.name}'" not in text:
            pets.write_text(PET_LINE.sub(lambda m: m.group(1) + entry + m.group(2), text))

        readme = mod / "README.md"
        line = f"- **`/pet {a.name}`:** Shows {a.display} every turn.\n"

        if readme.exists() and line not in readme.read_text():
            readme.write_text(re.sub(r"(- \*\*`/pet \w+`:\*\* Shows .*\n)(?!- \*\*`/pet \w+`:\*\* Shows)",
                                     lambda m: m.group(1) + line, readme.read_text(), count=1))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("name")
    p.add_argument("images", type=Path, help="folder holding every frame image")
    p.add_argument("--step", type=int, default=1, help="use every Nth frame, to match a slower frame speed")
    p.add_argument("--colors", type=int, default=DEFAULT_COLORS)
    p.add_argument("--display")
    p.add_argument("--kind", default="a dancing pixel pet")
    p.add_argument("--summary", default="dances in place")
    p.add_argument("--move", default="dance")
    p.add_argument("--seconds", type=float, default=0.1)
    p.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    p.add_argument("--key", default="#00ff00")
    a = p.parse_args()
    a.display = a.display or f"the {a.name} pet"
    mod = REPO / a.name

    if not re.fullmatch(r"[a-z][a-z0-9-]*", a.name) or mod.exists():
        sys.exit(f"{a.name!r} must be lowercase letters, digits or hyphens, and {mod} must not exist")

    files = sorted((f for f in a.images.iterdir() if f.suffix.lower() in (".png", ".webp", ".jpg", ".jpeg")), key=natural)

    files = files[::a.step]

    if not files:
        sys.exit(f"no images in {a.images}")

    key = tuple(int(a.key.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    grids = pixelate([key_frame(Image.open(f), key) for f in files], a.height)
    quantize(grids, a.colors)

    source = mod / "frames" / "source"
    source.mkdir(parents=True)

    for i, grid in enumerate(grids):
        (source / f"frame_{i:02d}.svg").write_text(source_svg(grid))

    for rel in COPIED:
        (mod / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(TEMPLATE / rel, mod / rel)
        (mod / rel).write_text(swap((mod / rel).read_text(), a))

    (mod / ".claude-plugin").mkdir()
    plugin = json.loads((TEMPLATE / ".claude-plugin/plugin.json").read_text())
    plugin.update(name=a.name, description=f"{a.display[:1].upper() + a.display[1:]}, {a.kind}, in the working row")
    (mod / ".claude-plugin/plugin.json").write_text(json.dumps(plugin) + "\n")
    (mod / "pet.json").write_text(json.dumps({
        "mod": a.name, "word": a.name, "name": a.display, "kind": a.kind, "summary": a.summary,
        "moves": [{"name": a.move, "frames": len(grids)}], "frame_seconds": a.seconds,
        "covers": [[f"{a.move}_00", a.move.capitalize(), a.move]]}, indent=2) + "\n")

    mods = sorted(d for d in REPO.iterdir() if (d / "hooks" / "pets.ts").exists())
    register(a, mods)
    print(subprocess.run([sys.executable, str(mod / "tools/build_frames.py"), str(source), str(mod)],
                         check=True, capture_output=True, text=True).stdout)


if __name__ == "__main__":
    main()
