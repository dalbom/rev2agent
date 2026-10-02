"""Slice 3x3 Reviewer 2 expression sheets into square avatar tiles and write a manifest.

Re-runnable: regenerates every tile, preview.png, and manifest.json from sheets/,
then exports round thumbnails and a copy of the manifest to the reviewer2 plugin.
The sheets and tiles are not in git; generate the sheets from PROMPTS.md first.
Run: micromamba run -n py313 python assets/avatars/slice_avatars.py
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
PLUGIN_AVATARS = ROOT.parents[1] / ".claude" / "skills" / "reviewer2" / "avatars"
SIZE = 384
BACKGROUND = "#0E2445"
RING = "#C8232A"
THUMB = 128  # twice the 56-64 CSS pixels the bubble draws it at
THUMB_COLORS = 48

# sheet file -> nine (id, korean label, tags) in reading order
SHEETS = {
    "sheet-a-basic.png": [
        ("stern", "기본 (팔짱 낀 심사위원)", ["neutral", "default", "judging", "stern"]),
        ("skeptical", "안경 너머 의심", ["skeptical", "really", "doubt", "review"]),
        ("grudging-nod", "마지못한 인정", ["approve", "ok", "grudging", "fine"]),
        ("laugh", "폭소", ["laugh", "funny", "sarcasm"]),
        ("surprised", "놀람", ["surprise", "unexpected", "wow"]),
        ("angry", "분노", ["angry", "annoyed", "furious"]),
        ("disappointed", "실망", ["disappointed", "sigh", "failed"]),
        ("thinking", "생각 중", ["thinking", "pondering", "hmm", "planning"]),
        ("yawn", "하품", ["tired", "bored", "late-night"]),
    ],
    "sheet-b-review.png": [
        ("reading", "원고 정독", ["reading", "review", "focus", "literature"]),
        ("red-pen", "빨간 펜", ["editing", "critique", "review", "writing"]),
        ("major-revisions", "MAJOR REVISIONS 판정", ["verdict", "major-revision", "reject", "review"]),
        ("accept", "마지못한 ACCEPT", ["verdict", "accept", "approve", "success"]),
        ("magnifier", "인용 검증", ["verify", "citation", "inspect", "suspicious"]),
        ("accusing", "지적", ["blame", "you", "critique", "warning"]),
        ("facepalm", "이마 짚기", ["facepalm", "exasperated", "silly-mistake"]),
        ("shrug", "납득 불가", ["unconvinced", "shrug", "unclear", "question"]),
        ("thumbs-down", "엄지 아래", ["reject", "bad", "disapprove"]),
    ],
    "sheet-c-research.png": [
        ("waiting", "시계 보기", ["waiting", "long-task", "experiment-running", "impatient"]),
        ("idea", "아이디어", ["idea", "suggestion", "eureka", "planning"]),
        ("cheer", "환호", ["success", "done", "tests-pass", "celebrate"]),
        ("confused", "갸우뚱", ["confused", "unclear", "question"]),
        ("thumbs-up", "엄지척", ["approve", "good", "ok", "lgtm"]),
        ("coffee", "커피 타임", ["break", "relaxed", "idle", "waiting"]),
        ("exhausted", "녹초", ["exhausted", "overwhelmed", "long-session"]),
        ("oops", "앗 실수", ["mistake", "bug", "error", "sorry"]),
        ("wave", "손 흔들기", ["hello", "bye", "greeting"]),
    ],
    "sheet-d-strong.png": [
        ("shocked", "충격", ["shock", "panic", "alarm"]),
        ("suspicious", "의심 곁눈질", ["suspicious", "doubt", "side-eye"]),
        ("eye-roll", "눈 굴리기", ["eye-roll", "sarcasm", "obviously"]),
        ("tsk", "쯧쯧", ["scold", "warning", "no-no"]),
        ("teary", "울먹", ["sad", "hurt", "rejected", "failed"]),
        ("smug", "의기양양", ["proud", "smug", "nailed-it"]),
        ("relieved", "안도", ["relief", "phew", "fixed"]),
        ("delighted", "기쁨", ["excited", "delighted", "anticipation"]),
        ("goodnight", "잘 자", ["goodnight", "sleep", "end-of-day"]),
    ],
}

# Tiles taken from a corrected sheet instead of the original: id -> (sheet file, tile index)
OVERRIDES = {}


def tile_spans(profile, thresh=235, min_len=100):
    """Return (start, end) runs where the profile is NOT a white gutter."""
    dark = profile < thresh
    spans, start = [], None
    for i, d in enumerate(dark):
        if d and start is None:
            start = i
        elif not d and start is not None:
            if i - start >= min_len:
                spans.append((start, i))
            start = None
    if start is not None and len(dark) - start >= min_len:
        spans.append((start, len(dark)))
    return spans


def slice_sheet(path):
    img = Image.open(path).convert("RGB")
    a = np.asarray(img, float)
    # A gutter line is bright in every channel across (nearly) the whole line.
    lum = a.min(axis=2)
    cols = tile_spans(np.percentile(lum, 20, axis=0))
    rows = tile_spans(np.percentile(lum, 20, axis=1))
    if len(cols) != 3 or len(rows) != 3:
        raise SystemExit(f"{path.name}: expected 3x3, found {len(rows)}x{len(cols)}: rows={rows} cols={cols}")
    tiles = []
    for y0, y1 in rows:
        for x0, x1 in cols:
            inset = 3  # shave anti-aliased gutter edge
            box = [x0 + inset, y0 + inset, x1 - inset, y1 - inset]
            w, h = box[2] - box[0], box[3] - box[1]
            side = min(w, h)
            box[0] += (w - side) // 2
            box[1] += (h - side) // 2
            tile = img.crop((box[0], box[1], box[0] + side, box[1] + side))
            tiles.append(tile.resize((SIZE, SIZE), Image.LANCZOS))
    return tiles


def circle_preview(tiles, cols=9, cell=96, gap=12):
    """Contact sheet of every avatar masked to a circle, as it would appear in a UI."""
    rows = -(-len(tiles) // cols)
    sheet = Image.new("RGB", (cols * (cell + gap) + gap, rows * (cell + gap) + gap), "#F4F4F0")
    mask = Image.new("L", (cell * 4, cell * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, cell * 4 - 1, cell * 4 - 1), fill=255)
    mask = mask.resize((cell, cell), Image.LANCZOS)
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        sheet.paste(tile.resize((cell, cell), Image.LANCZOS), (gap + c * (cell + gap), gap + r * (cell + gap)), mask)
    # Flat line art keeps its look at 64 colours, at a fraction of the size.
    return sheet.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)


def round_thumbnail(tile, size=THUMB, ring=RING, ss=4):
    """The tile cut to a circle with a red ring and transparent corners, palette-quantized."""
    big = size * ss
    face = tile.convert("RGBA").resize((big, big), Image.LANCZOS)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, big - 1, big - 1), fill=255)
    out = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    out.paste(face, (0, 0), mask)
    # PIL draws an outline inward from its box, so the same box covers the mask's edge.
    ImageDraw.Draw(out).ellipse((0, 0, big - 1, big - 1), outline=ring, width=3 * ss)
    out = out.resize((size, size), Image.LANCZOS)
    # Quantize the colours only and keep the full alpha channel: a palette with
    # alpha breaks the anti-aliased ring and edge into dashes.
    flat = out.convert("RGB").quantize(colors=THUMB_COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    thumb = flat.convert("RGB")
    thumb.putalpha(out.getchannel("A"))
    return thumb


def export_plugin(manifest, tiles):
    """Writes the plugin's avatars/: one round PNG per avatar and the manifest without build-only fields."""
    if PLUGIN_AVATARS.exists():
        shutil.rmtree(PLUGIN_AVATARS)
    PLUGIN_AVATARS.mkdir(parents=True)
    for entry, tile in zip(manifest["avatars"], tiles):
        round_thumbnail(tile).save(PLUGIN_AVATARS / entry["file"], optimize=True)
    exported = {
        "character": manifest["character"],
        "size": THUMB,
        "default": manifest["default"],
        "avatars": [{k: a[k] for k in ("id", "file", "label_ko", "tags")} for a in manifest["avatars"]],
    }
    (PLUGIN_AVATARS / "manifest.json").write_text(json.dumps(exported, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    manifest = {
        "character": "Reviewer 2 (Rev2Agent mascot, based on logo.png)",
        "size": SIZE,
        "background": BACKGROUND,
        "default": "stern",
        "usage": "Pick an avatar by matching the message's mood to `tags` (choose at random among matches); fall back to `default`. "
        "Files are 384x384 PNG on a flat navy backdrop, suited to a circular mask.",
        "avatars": [],
    }
    cache, missing, made = {}, [], []

    def tiles_of(sheet):
        if sheet not in cache:
            cache[sheet] = slice_sheet(ROOT / "sheets" / sheet)
        return cache[sheet]

    for sheet, entries in SHEETS.items():
        if not (ROOT / "sheets" / sheet).exists():
            missing.append(sheet)
            continue
        for index, (ident, ko, tags) in enumerate(entries):
            src, idx = OVERRIDES.get(ident, (sheet, index))
            if not (ROOT / "sheets" / src).exists():
                src, idx = sheet, index
            tile = tiles_of(src)[idx]
            name = f"{ident}.png"
            tile.save(ROOT / name, optimize=True)
            made.append(tile)
            manifest["avatars"].append({"id": ident, "file": name, "label_ko": ko, "tags": tags, "sheet": src})
    ids = [a["id"] for a in manifest["avatars"]]
    assert len(ids) == len(set(ids)), "duplicate avatar ids"
    if made:
        circle_preview(made).save(ROOT / "preview.png", optimize=True)
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    export_plugin(manifest, made)
    print(f"wrote {len(ids)} avatars; missing sheets: {missing or 'none'}; plugin thumbnails in {PLUGIN_AVATARS}")


if __name__ == "__main__":
    sys.exit(main())
