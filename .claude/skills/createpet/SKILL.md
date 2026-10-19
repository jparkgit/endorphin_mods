---
name: createpet
description: Creates a new pixel-pet mod, mirroring pixel-kitty, from a folder of animation frame images on a solid-color background, and makes it selectable with /pet <name>. Use when the user types /createpet, or asks to make, add or create a new pet from frames, a gif split or a folder of images.
---

# createpet

Arguments: the pet name (lowercase letters, digits, hyphens). Then ask the user for the **path of the folder holding all the frame images**. Never ask for attachments, since attachments arrive in limited numbers.

## Steps

1. Ask for the folder path if not given. List it and count the images.
2. Ask only what the user has not said: display name (default `the <name> pet`), kind (for example `a dancing pixel kitten`), background color (default `#00ff00`), and a frame step. The step is the source frame delay divided by 0.1 s, rounded. A delay of 0.03 s means `--step 3`.
3. Run the script. It is bundled, so run it and do not read it:

```bash
python3 -I .claude/skills/createpet/scripts/createpet.py <name> "<folder>" --display "<display>" --kind "<kind>" --step <n>
```

Options: `--move` (default `dance`), `--seconds` per frame (default 0.1), `--height` in cells (default 42, pixel-kitty's), `--colors` (default 24), `--key` background color.

The script keys out the background, pixelates every frame at one shared cell size, writes `<name>/frames/source/*.svg`, copies pixel-kitty's mod files, builds `hooks/moves.ts`, `hooks/frames_*.ts` and the preview SVGs in `<name>/frames/`, and adds the pet to `PETS` in every mod's `hooks/pets.ts` so `/pet <name>` works.

## Verify

1. The last line of output must show a frame count, `<width> x 42` and about 1 Svg page. If it errors or shows more pages, lower `--colors` or raise `--step`, delete `<name>/`, run `git checkout` on the other mods, and rerun.
2. Open `<name>/frames/loop.svg` in a browser and look for leftover background or lost detail. If the background remains, pass `--key`.
3. Check `git diff` shows only the new `PETS` line and `/pet` README line in the other mods.
