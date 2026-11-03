#!/usr/bin/env python3
"""
Flow Labs Content Factory
=========================
Generates a ready-to-post 3-day social pack in Hinglish, roast tone.

  START-HERE.md      exact posting steps, order, times
  VIRAL-PLAYBOOK.md  hooks, keywords, hashtags, first-60-minutes plan
  plan.md            strategy, category mix, voice split, targets
  calendar.csv       importable schedule
  captions.md        every caption in one place
  day-1/ ... day-3/
      video.mp4      animated 9:16 reel, 1080x1920, voiceover + burned-in text
      video.srt      subtitle file
      video-cover.jpg
      script.md      scene-by-scene script with timecodes
      caption.txt    Instagram caption (with website)
      hashtags.txt   first comment: hashtags + search keywords
      threads.txt    Threads post
      linkedin.txt   LinkedIn post
      carousel.md    slide-by-slide carousel
      stories.txt    2 story prompts

Usage:
    python run.py
    python run.py --days 3 --start 2026-11-04
    python run.py --skip-video
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

import voice as voicepipe

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
CONFIG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
BANK = json.loads((HERE / "content_bank.json").read_text(encoding="utf-8"))

W, H = 1080, 1920
FPS = 30


def _font_file(*names: str, bold: bool = False) -> str:
    """First font that actually exists on this machine.

    Keeps the look identical on a normal Windows box, but a machine with a
    different Windows variant, or a teammate on Linux/Mac, gets a sane
    fallback instead of a hard crash.
    """
    dirs = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts",
        Path(os.environ.get("WINDIR", "/Windows")) / "Fonts",
        Path("/usr/share/fonts"),
        Path("/Library/Fonts"),
    ]
    wanted = [n for n in names if n]
    folders: list[Path] = []
    for d in dirs:
        if d.exists() and d not in folders:
            folders.append(d)
    for folder in folders:
        for n in wanted:
            p = folder / n
            if p.exists():
                return str(p)
        for n in wanted:                           # recursive search, deeper trees
            hits = list(folder.rglob(n))
            if hits:
                return str(hits[0])

    # nothing matched - let PIL pick any ttf it can find, or raise a clear error
    for folder in folders:
        for p in folder.rglob("*.tt[fco]"):
            return str(p)
    raise RuntimeError(
        "No usable .ttf fonts found. Install Segoe UI (fonts/segoeuib.ttf, "
        "seguisb.ttf) or any system font set, then re-run."
    )


FONT_BOLD = _font_file("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")
FONT_SEMI = _font_file("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans.ttf")

C = CONFIG["colors"]
ACCENT = C["accent"]
TEXT = C["text"]
MUTED = C["muted"]
BG = C["bg"]
WEBSITE = CONFIG.get("website", "")

CAT_LABEL = {"education": "EDUCATION", "case_study": "CASE STUDY", "other": "ROAST"}


# --------------------------------------------------------------------------
# shell helpers
# --------------------------------------------------------------------------

def run(cmd: list[str]) -> None:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"command failed:\n{' '.join(cmd)}\n{p.stderr[-1200:]}")


def probe(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(p.stdout.strip())


def ffmpeg_exists() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------
# image helpers
# --------------------------------------------------------------------------

def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (W, H), bottom)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)],
               fill=tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3)))
    return img


def photo_layer(path: Path) -> Image.Image | None:
    try:
        ph = Image.open(path).convert("RGB")
    except Exception:
        return None
    ph = ImageOps.fit(ph, (W, H), Image.LANCZOS)
    ph = ph.filter(ImageFilter.GaussianBlur(22))
    dark = Image.new("RGB", (W, H), hex_rgb(BG))
    return Image.blend(ph, dark, 0.70)


def add_grain(img: Image.Image, amount: float = 0.035) -> Image.Image:
    noise = Image.effect_noise((W, H), 22).convert("RGB")
    return Image.blend(img, noise, amount)


def add_vignette(img: Image.Image, floor: float = 0.40) -> Image.Image:
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-W * 0.30, -H * 0.20, W * 1.30, H * 1.20], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(240))
    lo = int(255 * floor)
    mask = mask.point(lambda v: lo + int(v * (255 - lo) / 255))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(img, black, mask)


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        cur = ""
        for word in para.split():
            trial = (cur + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines


def fit_text(draw, text, max_w, max_h, start, minimum=40, bold=True):
    size = start
    path = FONT_BOLD if bold else FONT_SEMI
    while size >= minimum:
        font = ImageFont.truetype(path, size)
        lines = wrap(draw, text, font, max_w)
        lh = int(size * 1.26)
        if lh * len(lines) <= max_h:
            return font, lines, lh
        size -= 4
    font = ImageFont.truetype(path, minimum)
    return font, wrap(draw, text, font, max_w), int(minimum * 1.26)


def render_background(out: Path, kind: str, day_no: int, total: int,
                      photo: Path | None, category: str) -> None:
    """Static layer: gradient/photo, grain, vignette, wordmark, footer, dots."""
    if kind == "cta":
        img = gradient(hex_rgb("#B32220"), hex_rgb("#6f1211"))
        main = hex_rgb(TEXT)
    else:
        img = gradient((13, 13, 10), hex_rgb(BG))
        if photo:
            layer = photo_layer(photo)
            if layer:
                img = Image.blend(img, layer, 0.55)
                # keep the photo as texture, never as a mid-grey backdrop for white text
                img = img.point(lambda v: int(v * 0.58))
        main = hex_rgb(TEXT)

    img = add_grain(img)
    if kind != "cta":
        img = add_vignette(img)

    d = ImageDraw.Draw(img)

    # wordmark
    label_font = ImageFont.truetype(FONT_SEMI, 27)
    d.text((W / 2, 108), "T H E   F L O W   L A B S", font=label_font,
           fill=(196, 190, 182) if kind == "cta" else hex_rgb(MUTED), anchor="mm")

    # category pill
    if kind != "cta" and category in CAT_LABEL:
        txt = CAT_LABEL[category]
        pf = ImageFont.truetype(FONT_SEMI, 24)
        tw = d.textlength(txt, font=pf)
        box = [W / 2 - tw / 2 - 24, 152, W / 2 + tw / 2 + 24, 202]
        d.rounded_rectangle(box, radius=25, outline=hex_rgb(MUTED), width=2)
        d.text((W / 2, 177), txt, font=pf, fill=hex_rgb(MUTED), anchor="mm")

    # footer
    foot = ImageFont.truetype(FONT_SEMI, 34)
    if kind == "cta":
        site_font = ImageFont.truetype(FONT_SEMI, 27)
        site = WEBSITE.replace("https://", "").replace("http://", "").rstrip("/")
        d.text((W / 2, 1640), site, font=site_font, fill=(240, 225, 220), anchor="mm")
    d.text((W / 2, 1738), CONFIG["handle"], font=foot,
           fill=(245, 240, 233) if kind == "cta" else hex_rgb(MUTED), anchor="mm")

    # progress dots
    gap = 26
    x0 = W / 2 - (total - 1) * gap / 2
    for i in range(total):
        cx = x0 + i * gap
        if i == day_no:
            d.ellipse([cx - 6, 1794, cx + 6, 1806],
                      fill=(245, 240, 233) if kind == "cta" else hex_rgb(TEXT))
        else:
            d.ellipse([cx - 4, 1796, cx + 4, 1804],
                      fill=(170, 90, 90) if kind == "cta" else (86, 86, 80))

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


def render_text_layer(out: Path, text: str, kind: str) -> None:
    """Transparent layer: accent rule + headline. Slides up over the background."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    main = hex_rgb(TEXT) + (255,)
    accent = hex_rgb(ACCENT) + (255,)

    if kind == "list":
        title, _, rest = text.partition("\n")
        items = [ln.strip() for ln in rest.split("\n") if ln.strip()]
        num_font = ImageFont.truetype(FONT_SEMI, 54)
        text_x = 236
        max_w = W - text_x - 96

        blocks = []
        for it in items:
            m = re.match(r"^(\d+)\.\s*(.*)$", it)
            num, body = (m.group(1), m.group(2)) if m else ("", it)
            font, lines, lh = fit_text(d, body, max_w, 300, 62, minimum=34)
            blocks.append((num, font, lines, lh))

        item_gap = 36
        total_h = sum(b[3] * len(b[2]) for b in blocks) + item_gap * (len(blocks) - 1)
        top = (H - total_h) / 2 - 20

        title_font = ImageFont.truetype(FONT_SEMI, 50)
        d.text((W / 2, top - 88), title, font=title_font, fill=accent, anchor="mm")
        d.rectangle([W / 2 - 60, top - 150, W / 2 + 60, top - 142], fill=accent)

        y = top
        for num, font, lines, lh in blocks:
            if num:
                d.text((text_x - 64, y + lh / 2), f"{num}.",
                       font=num_font, fill=accent, anchor="lm")
            for line in lines:
                d.text((text_x, y + lh / 2), line, font=font, fill=main, anchor="lm")
                y += lh
            y += item_gap
    else:
        start_size = {"hook": 104, "body": 80, "cta": 88}.get(kind, 80)
        font, lines, lh = fit_text(d, text, 880, 900, start_size, minimum=40)
        block_h = lh * len(lines)
        top = (H - block_h) / 2 - 60

        if kind != "cta":
            d.rectangle([W / 2 - 60, top - 62, W / 2 + 60, top - 54], fill=accent)

        y = top
        for line in lines:
            if line:
                d.text((W / 2, y + lh / 2), line, font=font, fill=main, anchor="mm")
            y += lh

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


# --------------------------------------------------------------------------
# audio + video
# --------------------------------------------------------------------------

def tts(text: str, out: Path, v: dict) -> None:
    voicepipe.speak(text, out, v["voice"], v["rate"], v["pitch"])


def scene_clip(bg: Path, tx: Path, mp3: Path, dur: float, out: Path,
               bar_color: str) -> None:
    frames = max(int(round(dur * FPS)), FPS)
    fade_out = max(dur - 0.34, 0.10)

    fc = (
        "[0:v]scale=1188:2112,"
        f"zoompan=z='min(1+0.00045*on,1.10)'"
        ":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1080x1920:fps={FPS},format=rgba[b];"
        "[1:v]format=rgba,"
        "fade=t=in:st=0.08:d=0.38:alpha=1,"
        f"fade=t=out:st={fade_out:.2f}:d=0.28:alpha=1[t];"
        "[b][t]overlay=eval=frame:x=0:y='34*max(0,1-t/0.50)':format=auto[o];"
        f"[o]drawbox=x=0:y=0:w='iw*min(t/{dur:.3f},1)':h=6:"
        f"color={bar_color}@0.90:t=fill,format=yuv420p[v];"
        "[2:a]apad=pad_dur=0.55,aresample=44100,aformat=channel_layouts=stereo[a]"
    )

    run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(bg),
        "-loop", "1", "-framerate", str(FPS), "-i", str(tx),
        "-i", str(mp3),
        "-t", f"{dur:.3f}",
        "-filter_complex", fc,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-x264-params", "aq-mode=3",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "128k",
        str(out),
    ])


def concat_clips(clips: list[Path], out: Path) -> None:
    lst = out.parent / "concat.txt"
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips), encoding="utf-8")
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(out)])


def write_srt(scenes: list[dict], durs: list[float], path: Path) -> None:
    def ts(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int(round((t - math.floor(t)) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    lines = []
    t = 0.0
    for i, (sc, d) in enumerate(zip(scenes, durs), 1):
        lines.append(f"{i}\n{ts(t)} --> {ts(t + d)}\n{sc['voice']}\n")
        t += d
    path.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# selection
# --------------------------------------------------------------------------

def weighted_sequence(weights: list[float], n: int) -> list[int]:
    """Order n picks so the running counts track the given weights."""
    total = sum(weights) or 1.0
    counts = [0] * len(weights)
    seq: list[int] = []
    for k in range(n):
        best = max(range(len(weights)),
                   key=lambda i: weights[i] / total * (k + 1) - counts[i])
        counts[best] += 1
        seq.append(best)
    return seq


def voice_sequence(n: int) -> list[dict]:
    mix = CONFIG.get("voice_mix") or [
        {"voice": CONFIG["voice"], "weight": 1.0,
         "rate": CONFIG["voice_rate"], "pitch": CONFIG.get("voice_pitch", "+0Hz")}
    ]
    return [mix[i] for i in weighted_sequence([m["weight"] for m in mix], n)]


def pick_by_category(n: int, rng: random.Random) -> list[dict]:
    mix = CONFIG.get("category_mix") or {}
    angles = BANK["angles"]
    if not mix:
        pool = angles[:]
        rng.shuffle(pool)
        return [pool[i % len(pool)] for i in range(n)]

    cats = list(mix.keys())
    order = weighted_sequence([mix[c] for c in cats], n)

    pools: dict[str, list[dict]] = {}
    for a in angles:
        pools.setdefault(a.get("category", "other"), []).append(a)
    for c in cats:
        rng.shuffle(pools.get(c, []))

    used = {c: 0 for c in cats}
    picked = []
    for idx in order:
        c = cats[idx]
        pool = pools.get(c) or angles
        picked.append(pool[used[c] % len(pool)])
        used[c] += 1
    return picked


# --------------------------------------------------------------------------
# content
# --------------------------------------------------------------------------

def estimate(text: str) -> float:
    return max(2.2, len(text.split()) / 2.7 + 0.6)


def build_day(angle: dict, d: date, idx: int, rng: random.Random, voice: dict) -> dict:
    fixes = angle["fixes"]
    category = angle.get("category", "other")
    keywords = angle.get("keywords", [])

    list_title = "3 fixes. Free mein."
    list_text = list_title + "\n" + "\n".join(f"{i + 1}. {f}" for i, f in enumerate(fixes))

    scenes = [
        {"kind": "hook", "cat": "other", "screen": angle["hook"], "voice": angle["hook"]},
        {"kind": "body", "cat": "education", "screen": angle["problem"], "voice": angle["problem"]},
        {"kind": "list", "cat": "education", "screen": list_text,
         "voice": f"Teen fixes, free mein. {fixes[0]}. {fixes[1]}. {fixes[2]}."},
        {"kind": "body", "cat": "case_study", "screen": angle["proof"], "voice": angle["proof"]},
        {"kind": "cta", "cat": "other", "screen": angle["cta"], "voice": angle["cta"]},
    ]

    tags = " ".join(angle["tags"])
    kw_line = ", ".join(keywords) if keywords else ""

    caption = (
        f"{angle['hook']}\n\n"
        f"{angle['problem']}\n\n"
        "3 fixes, free mein:\n"
        f"1. {fixes[0]}\n2. {fixes[1]}\n3. {fixes[2]}\n\n"
        f"{angle['proof']}\n\n"
        f"{angle['cta']}\n\n"
        f"Site: {WEBSITE}\n"
        "(link in bio)"
    )

    hashtags = (
        f"{tags}\n\n"
        f"Search keywords: {kw_line}\n"
    )

    threads = (
        f"{angle['hook']}\n\n"
        f"{angle['problem']}\n\n"
        f"{fixes[0]}\n{fixes[1]}\n{fixes[2]}\n\n"
        f"{angle['cta']}"
    )

    linkedin = (
        f"{angle['hook']}\n\n"
        f"{angle['problem']}\n\n"
        "3 cheezein jo main is hafte badalunga:\n\n"
        f"1. {fixes[0]}\n2. {fixes[1]}\n3. {fixes[2]}\n\n"
        f"{angle['proof']}\n\n"
        f"{angle['cta']}\n\n"
        f"{WEBSITE}\n\n"
        f"{tags}"
    )

    carousel = [
        {"title": angle["hook"], "body": "Swipe. Teen fixes, free mein."},
        {"title": "Problem", "body": angle["problem"]},
        {"title": "Fix 1", "body": fixes[0]},
        {"title": "Fix 2", "body": fixes[1]},
        {"title": "Fix 3", "body": fixes[2]},
        {"title": "Result", "body": angle["proof"]},
        {"title": "Next step", "body": f"{angle['cta']}\n\n{WEBSITE}"},
    ]

    stories = rng.sample(BANK["story_prompts"], 2)

    return {
        "date": d,
        "index": idx,
        "theme": angle["theme"],
        "angle_id": angle["id"],
        "category": category,
        "keywords": keywords,
        "voice": voice,
        "scenes": scenes,
        "caption": caption,
        "hashtags": hashtags,
        "threads": threads,
        "linkedin": linkedin,
        "carousel": carousel,
        "stories": stories,
        "tags": tags,
    }


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------

def fmt_time(sec: float) -> str:
    return f"{int(sec // 60)}:{int(sec % 60):02d}"


def write_day(day: dict, out: Path, durs: list[float]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "caption.txt").write_text(day["caption"], encoding="utf-8")
    (out / "hashtags.txt").write_text(day["hashtags"], encoding="utf-8")
    (out / "threads.txt").write_text(day["threads"], encoding="utf-8")
    (out / "linkedin.txt").write_text(day["linkedin"], encoding="utf-8")
    (out / "stories.txt").write_text(
        "STORY 1 (11:00)\n" + day["stories"][0] + "\n\nSTORY 2 (18:00)\n" + day["stories"][1] + "\n",
        encoding="utf-8",
    )

    car = ["# Carousel\n"]
    for i, slide in enumerate(day["carousel"], 1):
        car.append(f"## Slide {i}\n**{slide['title']}**\n\n{slide['body']}\n")
    (out / "carousel.md").write_text("\n".join(car), encoding="utf-8")

    t = 0.0
    rows = []
    for i, (sc, dur) in enumerate(zip(day["scenes"], durs), 1):
        beat = "CTA (other)" if sc["kind"] == "cta" else CAT_LABEL.get(sc.get("cat", ""), "")
        rows.append(
            f"### Scene {i} - {sc['kind']} ({fmt_time(t)} - {fmt_time(t + dur)})  \n"
            f"*beat: {beat}*\n\n"
            f"**On screen**\n\n```\n{sc['screen']}\n```\n\n"
            f"**Voiceover**\n\n> {sc['voice']}\n"
        )
        t += dur

    script = (
        f"# Day {day['index'] + 1} - {day['theme']}\n\n"
        f"**Date:** {day['date'].strftime('%A, %d %B %Y')}  \n"
        f"**Category:** {CAT_LABEL.get(day['category'], day['category'])}  \n"
        f"**Runtime:** {fmt_time(t)}  \n"
        f"**Format:** 9:16 vertical, 1080x1920  \n"
        f"**Voice:** {day['voice']['voice']}  \n"
        f"**Keywords:** {', '.join(day['keywords'])}\n\n"
        + "\n".join(rows)
    )
    (out / "script.md").write_text(script, encoding="utf-8")


def write_root(days: list[dict], out: Path, cfg: dict) -> None:
    pt = cfg["post_times"]

    cal_rows = []
    for i, day in enumerate(days, 1):
        ds = day["date"].isoformat()
        cal_rows += [
            [ds, pt["linkedin"], "LinkedIn", "text post", f"day-{i}/linkedin.txt", ""],
            [ds, pt["threads"], "Threads", "text post", f"day-{i}/threads.txt", ""],
            [ds, pt["instagram_carousel"], "Instagram", "carousel", f"day-{i}/carousel.md", "optional"],
            [ds, pt["instagram_reel"], "Instagram", "reel", f"day-{i}/video.mp4", "primary"],
            [ds, pt["story_1"], "Instagram", "story", f"day-{i}/stories.txt", ""],
            [ds, pt["story_2"], "Instagram", "story", f"day-{i}/stories.txt", ""],
        ]

    with open(out / "calendar.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "time_ist", "platform", "format", "asset", "priority"])
        w.writerows(cal_rows)

    # plan.md
    lines = [
        "# 3-Day Content Plan",
        "",
        f"**Brand:** {cfg['brand']}  ",
        f"**Handle:** {cfg['handle']}  ",
        f"**Site:** {WEBSITE}  ",
        f"**Window:** {days[0]['date'].strftime('%d %b')} - {days[-1]['date'].strftime('%d %b %Y')}  ",
        f"**Timezone:** {cfg['timezone']}  ",
        f"**Language:** Hinglish (Roman script)  ",
        f"**Tone:** {cfg.get('tone', 'roast, meme, playful')}",
        "",
        "## What this pack is built to do",
        "",
        "- One idea per day, not five half-ideas.",
        "- Every video uses the same five beats: roast hook, problem, three fixes, proof, CTA.",
        "- The 40/20/40 mix is baked into every video: roast hook + CTA (other 40), why it happens + three fixes (education 40), proof (case study 20).",
        "- Every post has exactly one action. Comment a keyword, or DM.",
        "- The CTA keyword changes daily so you can see which topic pulls.",
        "",
        "## The three days",
        "",
        "| Day | Category | Theme | CTA keyword | Voice | Reel time |",
        "|---|---|---|---|---|---|",
    ]
    for i, day in enumerate(days, 1):
        m = re.search(r"(?:Comment|DM)\s+([A-Z]{2,})", day["caption"])
        kw = m.group(1) if m else cfg.get("cta_keyword", "SITE")
        vname = day["voice"]["voice"].replace("en-IN-", "").replace("Neural", "")
        lines.append(
            f"| {i} | {CAT_LABEL.get(day['category'], day['category'])} | {day['theme']} "
            f"| {kw} | {vname} | {pt['instagram_reel']} |"
        )

    lines += [
        "",
        "## The 40/20/40 mix (inside every video)",
        "",
        "| Beat | On-screen pill | Category |",
        "|---|---|---|",
        "| 1. Roast hook | ROAST | other |",
        "| 2. Why it happens | EDUCATION | education |",
        "| 3. Three fixes | EDUCATION | education |",
        "| 4. Proof | CASE STUDY | case study |",
        "| 5. CTA | (closing) | other |",
        "",
        "That is 2 education, 1 case study, 2 other = **40 / 20 / 40 in every single video**, "
        "on every platform. Same tone throughout: roast hook, dry explanation, proof, playful CTA.",
        "",
        "## Which angle leads each day",
        "",
        "| Setting | Target | This pack |",
        "|---|---|---|",
        f"| Education | 40% | {sum(1 for d in days if d['category'] == 'education')}/{len(days)} |",
        f"| Case study | 20% | {sum(1 for d in days if d['category'] == 'case_study')}/{len(days)} |",
        f"| Other (roast/meme) | 40% | {sum(1 for d in days if d['category'] == 'other')}/{len(days)} |",
        "",
        "A 3-day pack rounds to one of each; a 5-day pack lands on 2/1/2 and a month lands on "
        "exactly 40/20/40.",
        "",
        "## Voice split",
        "",
        "| Voice | Target | This pack |",
        "|---|---|---|",
        f"| Neerja Expressive (female) | 60% | {sum(1 for d in days if 'Neerja' in d['voice']['voice'])}/{len(days)} |",
        f"| Prabhat (male) | 40% | {sum(1 for d in days if 'Prabhat' in d['voice']['voice'])}/{len(days)} |",
        "",
        "A 3-day pack alternates (Neerja, Prabhat, Neerja); a 5-day pack hits 60/40 exactly.",
        "",
        "## Weekly rhythm this fits into",
        "",
        "| Platform | Volume | Job |",
        "|---|---|---|",
        "| Instagram reels | 3 in 3 days (then 2/week) | reach + DM conversations |",
        "| Instagram carousels | 1/day, optional | saves + authority |",
        "| Threads | 1/day | opinions, replies, profile visits |",
        "| LinkedIn | 1/day | B2B trust, startup leads |",
        "| Stories | 2/day | remind, poll, repost the reel |",
        "",
        "## Numbers to watch",
        "",
        "| Metric | Target |",
        "|---|---|",
        "| 3-second hold rate | above 55% |",
        "| Saves per reel | 5+ |",
        "| DM keyword replies | 3+ per post |",
        "| Profile visits | 30+ per reel |",
        "| Calls booked from this pack | 1-2 |",
        "",
        "If a reel misses all four, change the hook first. Do not change the topic.",
    ]
    (out / "plan.md").write_text("\n".join(lines), encoding="utf-8")

    # captions.md
    cap = ["# Captions (copy-paste)\n"]
    for i, day in enumerate(days, 1):
        cap.append(f"## Day {i} - {day['date'].strftime('%d %b')} - {day['theme']}\n")
        cap.append("### Instagram reel\n```\n" + day["caption"] + "\n```\n")
        cap.append("### Instagram first comment (hashtags)\n```\n" + day["hashtags"] + "\n```\n")
        cap.append("### Threads\n```\n" + day["threads"] + "\n```\n")
        cap.append("### LinkedIn\n```\n" + day["linkedin"] + "\n```\n")
    (out / "captions.md").write_text("\n".join(cap), encoding="utf-8")

    # VIRAL-PLAYBOOK.md
    vir = [
        "# Viral Playbook",
        "",
        "The reel is already built. This is what decides whether it travels.",
        "",
        "## The 1.5-second rule",
        "",
        "A viewer decides in about 1.5 seconds. Your hook line is on screen and in the voice "
        "from frame one. Do not add an intro, a logo animation, or \"hi guys\".",
        "",
        "## Six levers that actually move a reel",
        "",
        "| Lever | What to do |",
        "|---|---|",
        "| Hook | The first line names a loss or a mistake. Never a benefit. |",
        "| Loop | The last line should make the first line land differently. Rewatch = reach. |",
        "| Specificity | Numbers, seconds, rupees. \"7.2 seconds\" beats \"slow\". |",
        "| Tension | Name the enemy (the 8k website guy, the 6-hour reply). Roast, do not insult. |",
        "| Native audio | Add a trending track at 10-15% volume inside Instagram. Never bake music in. |",
        "| First hour | Reply to every comment within 60 seconds, with a question. |",
        "",
        "## This pack's hooks",
        "",
        "| Day | Hook | Comment keyword |",
        "|---|---|---|",
    ]
    for i, day in enumerate(days, 1):
        m = re.search(r"(?:Comment|DM)\s+([A-Z]{2,})", day["caption"])
        kw = m.group(1) if m else cfg.get("cta_keyword", "SITE")
        vir.append(f"| {i} | {day['scenes'][0]['screen']} | {kw} |")

    vir += [
        "",
        "## Search keywords in this pack",
        "",
        "| Day | Keywords |",
        "|---|---|",
    ]
    for i, day in enumerate(days, 1):
        vir.append(f"| {i} | {', '.join(day['keywords'])} |")

    vir += [
        "",
        "Put these in your Instagram **name field** and bio, not only in hashtags. "
        "Instagram search reads the name field and caption text, not just hashtags.",
        "",
        "## Hashtag rule",
        "",
        "- 3 to 5 tags per post. More looks spammy in 2026 and does not help.",
        "- 2 niche (under 50k posts), 1 mid (50k-500k), 0-1 broad.",
        "- Rotate the set every post so you do not look automated.",
        "- Put them in the first comment, not the caption.",
        "",
        "## Posting mechanics",
        "",
        "1. Upload the mp4. Do not re-export or compress it again.",
        "2. Cover = `video-cover.jpg`.",
        "3. Caption = `caption.txt`. Website is already in it.",
        "4. First comment = `hashtags.txt`.",
        "5. Inside Instagram, add trending audio at 10-15% volume.",
        "6. Share to story 3 hours later with a \"watch this\" sticker.",
        "7. Pin the best comment on the reel.",
        "",
        "## The first 60 minutes",
        "",
        "| Minute | Action |",
        "|---|---|",
        "| 0-5 | Reply to the first 3 comments with a question back |",
        "| 5-20 | DM every keyword commenter with the promised asset |",
        "| 20-40 | Comment on 10 accounts in your niche (real comments, not emojis) |",
        "| 40-60 | Post the reel to your story, then check saves |",
        "",
        "## Loop trick for these three",
        "",
        "- Day 1 ends on a CTA. Cut the last 0.5s in Instagram trim so the hook replays cleanly.",
        "- Day 2's proof line can be reused as the Day 3 hook. Familiarity compounds.",
        "- Day 3 ends the arc: roast, then proof, then the fix. Anyone who watched all three is a lead.",
        "",
        "## What not to do",
        "",
        "- No \"link in bio\" only. The website is written in the caption too.",
        "- No engagement pods, no bought likes, no comment bots. They kill reach.",
        "- No posting twice in one hour. Space the reel and the carousel.",
        "- No editing the caption in the first 30 minutes.",
    ]
    (out / "VIRAL-PLAYBOOK.md").write_text("\n".join(vir), encoding="utf-8")

    # START-HERE.md
    start = f"""# START HERE

Everything in this folder is ready. You only need to upload and reply.

## Folder map

```
{out.name}/
  START-HERE.md      this file
  VIRAL-PLAYBOOK.md  hooks, keywords, hashtags, first-60-minutes plan
  plan.md            3-day strategy and targets
  calendar.csv       schedule (import to Sheets if you want)
  captions.md        all captions in one place
  day-1/             video.mp4, script.md, caption.txt, hashtags.txt, carousel.md, threads.txt, linkedin.txt, stories.txt
  day-2/
  day-3/
```

## Posting order (IST)

| Time | Platform | What | File |
|---|---|---|---|
| {pt['linkedin']} | LinkedIn | text post | `day-N/linkedin.txt` |
| {pt['story_1']} | Instagram | story 1 | `day-N/stories.txt` |
| {pt['threads']} | Threads | text post | `day-N/threads.txt` |
| {pt['instagram_carousel']} | Instagram | carousel (optional) | `day-N/carousel.md` |
| {pt['story_2']} | Instagram | story 2 (teaser) | `day-N/stories.txt` |
| {pt['instagram_reel']} | Instagram | reel | `day-N/video.mp4` |

## How to post the reel

1. Copy `day-N/video.mp4` to your phone (AirDrop, USB, or WhatsApp to yourself).
2. Instagram -> Reel -> upload.
3. Cover: use `video-cover.jpg`.
4. Caption: paste `day-N/caption.txt`.
5. First comment: paste `day-N/hashtags.txt`. Keep hashtags out of the caption.
6. Inside Instagram, add a trending audio track at **10-15% volume**. Do not bake music into the file - native audio gets more reach.
7. Share the reel to your story 3 hours later with a "watch this" sticker.
8. Reply to every comment within 30 minutes. The first hour decides reach.

## How to post the carousel

1. Open `day-N/carousel.md`.
2. Build the slides in Canva (1080x1350) or ask me to render them.
3. Cover slide = the hook. Same caption as the reel, swap the first line if you post both.
4. Post at 13:00, not the same hour as the reel.

## How to post Threads

- Text only. No link in the first post.
- Paste `day-N/threads.txt`.
- Reply to 10 accounts in your niche right after posting.

## How to post LinkedIn

- Paste `day-N/linkedin.txt`.
- The website is already at the end of the post.
- Comment on 10 posts after publishing.

## The 30-minute rule

For 30 minutes after each post:

- Reply to every comment with a question back.
- DM anyone who comments a keyword within 5 minutes.
- Do not edit the post. Editing kills reach on some platforms.

## Daily checklist

- [ ] 09:00 LinkedIn posted
- [ ] 11:00 Story 1 posted
- [ ] 12:30 Threads posted + 10 replies
- [ ] 13:00 Carousel posted (optional)
- [ ] 18:00 Story 2 posted
- [ ] 19:30 Reel posted + hashtags in first comment
- [ ] 20:00 Shared reel to story
- [ ] 20:00-20:30 Replies done
- [ ] Log keyword replies in the CRM sheet

## If you only have 20 minutes today

Post the reel at 19:30 and reply for 20 minutes. Skip everything else. The reel is the asset.
"""
    (out / "START-HERE.md").write_text(start, encoding="utf-8")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=None, help="start date YYYY-MM-DD (default today)")
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--voice", default=None, help="force a single edge-tts voice id")
    ap.add_argument("--rate", default=None, help="e.g. +14%%")
    ap.add_argument("--pitch", default=None, help="e.g. +3Hz")
    args = ap.parse_args()

    if args.rate or args.pitch:
        for m in CONFIG.get("voice_mix", []):
            if args.rate:
                m["rate"] = args.rate
            if args.pitch:
                m["pitch"] = args.pitch
    if args.voice:
        CONFIG["voice_mix"] = [{
            "voice": args.voice, "weight": 1.0,
            "rate": args.rate or "+14%",
            "pitch": args.pitch or "+0Hz",
        }]

    start = date.fromisoformat(args.start) if args.start else date.today()
    seed = args.seed if args.seed is not None else int(start.strftime("%Y%m%d"))
    rng = random.Random(seed)

    picked = pick_by_category(args.days, rng)
    voices = voice_sequence(args.days)

    out = PROJECT / "content" / start.isoformat()
    out.mkdir(parents=True, exist_ok=True)

    print("Flow Labs Content Factory")
    print(f"  window : {start} -> {start + timedelta(days=args.days - 1)}")
    print(f"  output : {out}")
    print()

    days = [
        build_day(a, start + timedelta(days=i), i, rng, voices[i])
        for i, a in enumerate(picked)
    ]

    photos = sorted((PROJECT / "assets").glob("*.png"))
    do_video = not args.skip_video
    if do_video and not ffmpeg_exists():
        print("  ! ffmpeg not found - skipping video render")
        do_video = False

    for i, day in enumerate(days, 1):
        ddir = out / f"day-{i}"
        ddir.mkdir(parents=True, exist_ok=True)
        durs: list[float] = []
        vname = day["voice"]["voice"].replace("en-IN-", "").replace("Neural", "")

        if do_video:
            print(f"  day {i}: {day['theme']} [{day['category']}] voice={vname}")
            photo = photos[(i - 1) % len(photos)] if photos else None
            clips = []
            for j, sc in enumerate(day["scenes"]):
                bg = ddir / f"bg-{j + 1}.png"
                tx = ddir / f"tx-{j + 1}.png"
                mp3 = ddir / f"scene-{j + 1}.mp3"
                mp4 = ddir / f"scene-{j + 1}.mp4"

                render_background(bg, sc["kind"], i - 1, len(day["scenes"]),
                                  photo, sc.get("cat", day["category"]))
                render_text_layer(tx, sc["screen"], sc["kind"])
                tts(sc["voice"], mp3, day["voice"])
                dur = max(probe(mp3) + 0.45, 3.0)
                durs.append(dur)
                bar = "0xF2F0EC" if sc["kind"] == "cta" else "0xA31C1B"
                scene_clip(bg, tx, mp3, dur, mp4, bar)
                clips.append(mp4)
                print(f"    scene {j + 1}/{len(day['scenes'])}  {dur:.1f}s")

            concat_clips(clips, ddir / "video.mp4")
            write_srt(day["scenes"], durs, ddir / "video.srt")

            cover = Image.alpha_composite(
                Image.open(ddir / "bg-1.png").convert("RGBA"),
                Image.open(ddir / "tx-1.png").convert("RGBA"),
            )
            cover.convert("RGB").save(ddir / "video-cover.jpg", quality=92)
            (ddir / "video-cover.png").unlink(missing_ok=True)

            for p in list(ddir.glob("scene-*.mp4")) + list(ddir.glob("scene-*.mp3")):
                p.unlink(missing_ok=True)
            for p in list(ddir.glob("bg-*.png")) + list(ddir.glob("tx-*.png")):
                p.unlink(missing_ok=True)
            for p in list(ddir.glob("scene-*.png")):
                p.unlink(missing_ok=True)
            (ddir / "concat.txt").unlink(missing_ok=True)
        else:
            durs = [estimate(sc["voice"]) for sc in day["scenes"]]

        write_day(day, ddir, durs)
        print(f"  day {i}: done  ({fmt_time(sum(durs))})")

    write_root(days, out, CONFIG)

    print()
    print("Ready.")
    print(f"  open: {out / 'START-HERE.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
