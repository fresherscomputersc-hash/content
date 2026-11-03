#!/usr/bin/env python3
"""
Flow Labs - Site Autopsy
========================
Builds a reel from a *real* website: real screenshot, real measurements, real score.

Nobody can copy this format by prompting an AI, because the asset is the evidence.

    python autopsy.py --url https://example.com
    python autopsy.py --url https://example.com --name "Sharma Dental" --city Pune
    python autopsy.py --url https://example.com --skip-video

Output: ../../content/autopsy-<slug>/
    video.mp4  video.srt  video-cover.jpg  script.md
    caption.txt  hashtags.txt  score.json
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

import run as cf
import voice as voicepipe

W, H = cf.W, cf.H
ACCENT = cf.hex_rgb(cf.ACCENT)
TEXT = cf.hex_rgb(cf.TEXT)
MUTED = cf.hex_rgb(cf.MUTED)
BG = cf.hex_rgb(cf.BG)

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------

def find_browser() -> str:
    for p in CHROME_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError("Chrome or Edge not found. Install one, or pass --shot <png>.")


def capture(url: str, out: Path, width: int = 1280, height: int = 800) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    browser = find_browser()
    base = [
        browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
        "--no-sandbox", "--no-first-run", "--disable-extensions",
        f"--window-size={width},{height}",
        f"--screenshot={out}",
    ]
    # Some sites keep scheduling JS timers, which stalls --virtual-time-budget.
    # Try fast first, then progressively plainer strategies. Each attempt gets a
    # fresh profile so a stale lock from the previous one cannot block it.
    attempts = [
        (["--virtual-time-budget=9000"], 60),
        (["--timeout", "25000"], 75),   # real-time load cap, screenshot anyway
        ([], 90),                       # bare: wait for normal load events
    ]
    last_err: Exception | None = None
    for extra, tmo in attempts:
        profile = Path(tempfile.mkdtemp(prefix="fl-capture-"))
        cmd = base + extra + [f"--user-data-dir={profile}", url]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=tmo)
            if out.exists() and out.stat().st_size >= 2000:
                img = Image.open(out).convert("RGB")
                if img.size != (width, height):
                    img = ImageOps.fit(img, (width, height), Image.LANCZOS)
                    img.save(out)
                return
            last_err = RuntimeError("screenshot was empty or too small")
        except (subprocess.TimeoutExpired, OSError) as e:
            last_err = e
        finally:
            shutil.rmtree(profile, ignore_errors=True)
    raise RuntimeError(
        f"headless {Path(browser).stem} could not screenshot {url} "
        f"({last_err}). Workaround: AUTOPSY.bat --shot <your-own-png>"
    )


# --------------------------------------------------------------------------
# measure
# --------------------------------------------------------------------------

def _fetch(url: str, timeout: int = 15, head: bool = False) -> tuple[bytes, str, int]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "*/*"},
        method="HEAD" if head else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = b"" if head else r.read()
        size = int(r.headers.get("Content-Length") or len(body) or 0)
        return body, r.geturl(), size


def measure(url: str) -> dict:
    ttfb_samples: list[float] = []
    html = b""
    final = url

    # Warm-up hit: the first request pays DNS, TLS and a cold start, so scoring
    # it makes the number swing by 10+ points between runs. Discard it.
    try:
        _fetch(url, timeout=25)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"could not fetch {url}: {e}") from e
    time.sleep(0.5)

    for _ in range(5):
        t0 = time.perf_counter()
        try:
            html, final, _ = _fetch(url, timeout=20)
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"could not fetch {url}: {e}") from e
        ttfb_samples.append(time.perf_counter() - t0)
        time.sleep(0.4)

    # Best of 5, not median. Median drags in our own ISP jitter; the fastest
    # sample is the closest thing to what the server can actually do, and it is
    # the honest number to quote when we are scoring someone else's site.
    ttfb = min(ttfb_samples)

    text = html.decode("utf-8", "ignore")
    refs: set[str] = set()
    for m in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", text):
        raw = m.group(1).strip()
        if not raw or raw.startswith(("data:", "#", "mailto:", "tel:", "javascript:")):
            continue
        refs.add(urllib.parse.urljoin(final, raw))

    total = len(html)
    biggest_url, biggest = final, len(html)
    checked = 0
    for ref in list(refs)[:45]:
        try:
            _, _, size = _fetch(ref, timeout=8, head=True)
        except Exception:  # noqa: BLE001
            continue
        checked += 1
        total += size
        if size > biggest:
            biggest_url, biggest = ref, size

    return {
        "url": url,
        "final_url": final,
        "ttfb_s": round(ttfb, 2),
        "requests": checked + 1,
        "weight_kb": round(total / 1024),
        "biggest_kb": round(biggest / 1024),
        "biggest_name": urllib.parse.unquote(biggest_url.rsplit("/", 1)[-1])[:40] or "html",
    }


WEIGHTS = {"ttfb": 30, "weight": 25, "requests": 20, "biggest": 25}

# Coarse bands, not a continuous curve. A published score that moves 10 points
# between two runs is worthless - these buckets absorb measurement noise.
BANDS = {
    "ttfb": [(0.4, 1.00), (0.8, 0.85), (1.2, 0.70), (2.0, 0.45), (3.0, 0.20), (1e9, 0.0)],
    "weight": [(300, 1.00), (600, 0.85), (1000, 0.70), (2000, 0.45), (5000, 0.15), (1e9, 0.0)],
    "requests": [(30, 1.00), (50, 0.85), (80, 0.70), (120, 0.45), (150, 0.20), (1e9, 0.0)],
    "biggest": [(150, 1.00), (300, 0.85), (600, 0.70), (1000, 0.45), (2000, 0.15), (1e9, 0.0)],
}


def _bucket(key: str, value: float) -> float:
    for limit, factor in BANDS[key]:
        if value <= limit:
            return factor
    return 0.0


def subscores(m: dict) -> dict[str, float]:
    """Points earned per metric, so we can name the weakest one."""
    return {
        "ttfb": WEIGHTS["ttfb"] * _bucket("ttfb", m["ttfb_s"]),
        "weight": WEIGHTS["weight"] * _bucket("weight", m["weight_kb"]),
        "requests": WEIGHTS["requests"] * _bucket("requests", m["requests"]),
        "biggest": WEIGHTS["biggest"] * _bucket("biggest", m["biggest_kb"]),
    }


def flow_score(m: dict) -> int:
    """0-100, rounded to 5. Documented, not invented: see FLOW-SCORE.md."""
    return max(0, min(100, int(round(sum(subscores(m).values()) / 5) * 5)))


def worst_metric(m: dict) -> dict:
    """The weakest metric - the most defensible, most specific hook line."""
    scores = subscores(m)
    key = min(scores, key=scores.get)
    table = {
        "ttfb": {
            "short": f"server response {m['ttfb_s']}s",
            "voice": f"server response {m['ttfb_s']} second",
            "fix": (f"Server {m['ttfb_s']}s se 200ms pe laa. Caching on kar."),
        },
        "weight": {
            "short": f"page weight {m['weight_kb']} KB",
            "voice": f"page weight {m['weight_kb']} kilobyte",
            "fix": (f"Page {m['weight_kb']} KB hai. Images WebP kar, aadha ho jaayega."),
        },
        "requests": {
            "short": f"{m['requests']} requests",
            "voice": f"{m['requests']} requests",
            "fix": (f"{m['requests']} requests hain. Fonts aur scripts merge kar."),
        },
        "biggest": {
            "short": f"{m['biggest_name']} - {m['biggest_kb']} KB",
            "voice": f"sabse badi file {m['biggest_name']}, {m['biggest_kb']} kilobyte",
            "fix": (f"{m['biggest_name']} {m['biggest_kb']} KB ki hai. Pehle usko compress kar."),
        },
    }
    return {"key": key, **table[key]}


def verdict(score: int) -> tuple[str, str]:
    if score >= 70:
        return "HEALTHY", "Site theek hai. Ab traffic chahiye."
    if score >= 40:
        return "NEEDS SURGERY", "Kaam karegi, par customers kho rahi hai."
    return "EMERGENCY", "Har din customers chale ja rahe hain."


def hook_for(m: dict, score: int, label: str, subject: str) -> dict:
    """Score-driven hook. Roasting a 92/100 site reads fake, so don't."""
    worst = worst_metric(m)

    if score >= 70:
        return {
            "pill": "PROOF",
            "blocks": [("big", f"{subject} ne {score}/100 score kiya."),
                       ("accent", "Aaj roast nahi. Aaj proof.")],
            "voice": (f"{subject} ne {score} out of 100 score kiya. "
                      f"Aaj roast nahi, aaj proof. Server {m['ttfb_s']} second, "
                      f"page {m['weight_kb']} kilobyte. Isliye customer rukta hai."),
        }

    if score >= 40:
        return {
            "pill": "ROAST",
            "blocks": [("big", f"{subject} ka Flow Score sirf {score}/100 hai."),
                       ("accent", f"Sabse bada leak: {worst['short']}.")],
            "voice": (f"{subject} ka Flow Score sirf {score} out of 100 hai. "
                      f"Sabse bada leak: {worst['voice']}."),
        }

    return {
        "pill": "EMERGENCY",
        "blocks": [("big", f"{subject} ka server hi {m['ttfb_s']} second leta hai."),
                   ("accent", "Customer 3 second deta hai.")],
        "voice": (f"{subject} ka server {m['ttfb_s']} second leta hai. "
                  f"Customer 3 second deta hai. Wo nikal jaata hai."),
    }


# --------------------------------------------------------------------------
# drawing
# --------------------------------------------------------------------------

STAGE_BOX = (60, 212, W - 60, 872)
CHROME = 58
BAND_WINDOW = (890, 1660)      # where text sits under the browser window


def _glow(size: tuple[int, int]) -> Image.Image:
    """Soft red halo behind the browser window so the stage is not flat black."""
    small = (size[0] // 6, size[1] // 6)
    g = Image.new("RGB", small, (0, 0, 0))
    d = ImageDraw.Draw(g)
    cx, cy = small[0] / 2, small[1] * 0.26
    rx, ry = small[0] * 0.40, small[1] * 0.22
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(34, 8, 7))
    g = g.filter(ImageFilter.GaussianBlur(min(small) * 0.14))
    return g.resize(size, Image.LANCZOS)


def _browser(img: Image.Image, shot: Path, box: tuple[int, int, int, int],
             label: str, dim: float = 1.0, blur: float = 0.0,
             crop: tuple[float, float, float, float] | None = None) -> None:
    """Draw the target site inside a real browser window."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([x0 - 8, y0 - 8, x1 + 8, y1 + 8], radius=36,
                        fill=(20, 20, 18), outline=(255, 255, 255, 24), width=2)

    d.rounded_rectangle([x0, y0, x1, y0 + CHROME], radius=26, fill=(17, 17, 15))
    d.rectangle([x0, y0 + CHROME - 26, x1, y0 + CHROME], fill=(17, 17, 15))

    for i, c in enumerate([(198, 86, 80), (198, 162, 80), (112, 162, 112)]):
        cx = x0 + 36 + i * 30
        d.ellipse([cx - 8, y0 + CHROME / 2 - 8, cx + 8, y0 + CHROME / 2 + 8], fill=c)

    uf = ImageFont.truetype(cf.FONT_SEMI, 25)
    d.text((x0 + 152, y0 + CHROME / 2), label, font=uf,
           fill=(150, 146, 138), anchor="lm")

    s = Image.open(shot).convert("RGB")
    if crop:
        cw, ch = s.size
        s = s.crop((int(crop[0] * cw), int(crop[1] * ch),
                    int(crop[2] * cw), int(crop[3] * ch)))

    sw, sh = x1 - x0, y1 - y0 - CHROME
    s = ImageOps.fit(s, (sw, sh), Image.LANCZOS, centering=(0.5, 0.0))
    if blur > 0:
        s = s.filter(ImageFilter.GaussianBlur(blur))
    if dim < 1.0:
        s = Image.blend(s, Image.new("RGB", s.size, BG), 1 - dim)

    mask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, sw - 1, sh - 1], radius=16, fill=255)
    img.paste(s, (x0, y0 + CHROME), mask)


def stage(out: Path, day_no: int, total: int, pill: str,
          shot: Path | None = None, label: str = "", dim: float = 1.0,
          blur: float = 0.0, crop: tuple[float, float, float, float] | None = None,
          accent: bool = False, site_line: bool = False) -> None:
    """One background frame: dark stage, optional real browser window."""
    if accent:
        img = cf.gradient(cf.hex_rgb("#B32220"), cf.hex_rgb("#6f1211"))
    else:
        img = cf.gradient(cf.hex_rgb("#0b0b09"), cf.hex_rgb("#030302"))

    img = cf.add_grain(img)

    if shot is None:
        # Flat dark gradients band badly once H.264 quantises them. A sub-level
        # dither pass keeps the stage smooth after encoding.
        dither = Image.effect_noise((W, H), 10).convert("RGB")
        img = Image.blend(img, dither, 0.12)

    if shot is not None:
        img = ImageChops.add(img, _glow((W, H)))
        _browser(img, shot, STAGE_BOX, label, dim, blur, crop)

    img = cf.add_vignette(img)

    d = ImageDraw.Draw(img)
    fg = (200, 194, 186) if accent else MUTED
    d.text((W / 2, 92), "T H E   F L O W   L A B S",
           font=ImageFont.truetype(cf.FONT_SEMI, 27), fill=fg, anchor="mm")

    if pill:
        pf = ImageFont.truetype(cf.FONT_SEMI, 24)
        tw = d.textlength(pill, font=pf)
        d.rounded_rectangle([W / 2 - tw / 2 - 26, 136, W / 2 + tw / 2 + 26, 188],
                            radius=26, outline=fg, width=2)
        d.text((W / 2, 162), pill, font=pf, fill=fg, anchor="mm")

    if site_line:
        site = cf.CONFIG.get("website", "").replace("https://", "").replace("http://", "").rstrip("/")
        d.text((W / 2, 1628), site,
               font=ImageFont.truetype(cf.FONT_SEMI, 27), fill=(236, 220, 214), anchor="mm")

    d.text((W / 2, 1738), cf.CONFIG["handle"],
           font=ImageFont.truetype(cf.FONT_SEMI, 34), fill=fg, anchor="mm")

    gap = 26
    x0 = W / 2 - (total - 1) * gap / 2
    for i in range(total):
        cx = x0 + i * gap
        if i == day_no:
            d.ellipse([cx - 6, 1794, cx + 6, 1806], fill=(245, 240, 233) if accent else TEXT)
        else:
            d.ellipse([cx - 4, 1796, cx + 4, 1804], fill=(170, 90, 90) if accent else (86, 86, 80))

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


# --------------------------------------------------------------------------
# text layer
# --------------------------------------------------------------------------

def _measure(d, kind, payload, width):
    if kind == "big":
        font, lines, lh = cf.fit_text(d, payload, width, 700, 88, minimum=44)
        return font, lines, lh * len(lines)
    if kind == "accent":
        font, lines, lh = cf.fit_text(d, payload, width, 420, 58, minimum=34)
        return font, lines, lh * len(lines)
    if kind == "body":
        font, lines, lh = cf.fit_text(d, payload, width, 520, 48, minimum=30, bold=False)
        return font, lines, lh * len(lines)
    if kind == "hud":
        return None, None, len(payload) * 92
    if kind == "list":
        total = 0
        for item in payload:
            _, lines, lh = cf.fit_text(d, item, W - 190 - 90, 150, 52, minimum=30)
            total += lh * len(lines) + 38
        return None, None, total
    if kind == "score":
        return None, None, 470
    if kind == "gap":
        return None, None, payload
    return None, None, 0


def text_layer(out: Path, blocks: list[tuple[str, object]],
               on_accent: bool = False,
               band: tuple[int, int] | None = None) -> None:
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    main = (255, 255, 255, 255) if on_accent else TEXT + (255,)
    accent = (255, 255, 255, 255) if on_accent else ACCENT + (255,)
    soft = (255, 236, 232, 235) if on_accent else MUTED + (255,)

    width = 800
    heights = [_measure(d, k, p, width)[2] for k, p in blocks]
    total_h = sum(heights)
    if band:
        y = band[0] + max(0.0, (band[1] - band[0] - total_h) / 2)
    else:
        y = (H - total_h) / 2 - 40

    for (kind, payload), h in zip(blocks, heights):
        if kind == "gap":
            y += h
            continue

        if kind in ("big", "accent", "body"):
            font, lines, lh = _measure(d, kind, payload, width)
            if kind == "big":
                d.rectangle([W / 2 - 60, y - 46, W / 2 + 60, y - 38], fill=accent)
                y += 26
            for line in lines:
                if line:
                    d.text((W / 2, y + lh / 2), line, font=font,
                           fill=main if kind != "accent" else accent, anchor="mm")
                y += lh
            y += 14

        elif kind == "hud":
            label_font = ImageFont.truetype(cf.FONT_SEMI, 34)
            value_font = ImageFont.truetype(cf.FONT_BOLD, 54)
            for label, value in payload:
                cy = y + 46
                d.text((96, cy), label, font=label_font, fill=soft, anchor="lm")
                d.text((W - 96, cy), value, font=value_font, fill=accent, anchor="rm")
                d.line([(96, y + 88), (W - 96, y + 88)], fill=(255, 255, 255, 28), width=1)
                y += 92
            y += 8

        elif kind == "list":
            num_font = ImageFont.truetype(cf.FONT_SEMI, 50)
            text_x = 190
            for i, item in enumerate(payload, 1):
                font, lines, lh = cf.fit_text(d, item, W - text_x - 90, 150, 52, minimum=30)
                d.text((text_x - 56, y + 34), f"{i}.", font=num_font, fill=accent, anchor="lm")
                for line in lines:
                    d.text((text_x, y + 34), line, font=font, fill=main, anchor="lm")
                    y += lh
                y += 38
            y += 6

        elif kind == "score":
            value, label, note = payload
            cx, cy, r = W / 2, y + 210, 168
            box = [cx - r, cy - r, cx + r, cy + r]
            d.arc(box, 0, 360, fill=(255, 255, 255, 34), width=20)
            d.arc(box, -90, -90 + 360 * value / 100, fill=accent, width=20)

            num_font = ImageFont.truetype(cf.FONT_BOLD, 150)
            d.text((cx, cy - 10), str(value), font=num_font, fill=main, anchor="mm")
            small = ImageFont.truetype(cf.FONT_SEMI, 34)
            d.text((cx, cy + 92), "/ 100", font=small, fill=soft, anchor="mm")

            lf = ImageFont.truetype(cf.FONT_SEMI, 40)
            d.text((cx, cy + r + 62), label, font=lf, fill=accent, anchor="mm")
            nf = ImageFont.truetype(cf.FONT_SEMI, 36)
            lines = cf.wrap(d, note, nf, 760)
            yy = cy + r + 122
            for line in lines:
                d.text((cx, yy), line, font=nf, fill=soft, anchor="mm")
                yy += 46
            y += 470

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def build(url: str, name: str, city: str, shot: Path | None, skip_video: bool) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or urllib.parse.urlparse(url).netloc).lower()).strip("-")
    out = cf.PROJECT / "content" / f"autopsy-{slug}"
    out.mkdir(parents=True, exist_ok=True)

    print("Flow Labs - Site Autopsy")
    print(f"  target : {url}")

    shot_path = shot or (out / "site.png")
    if shot is None:
        capture(url, shot_path)
    print(f"  shot   : {shot_path}")

    m = measure(url)
    score = flow_score(m)
    label, note = verdict(score)
    print(f"  ttfb   : {m['ttfb_s']}s   weight: {m['weight_kb']} KB   "
          f"requests: {m['requests']}   biggest: {m['biggest_kb']} KB")
    print(f"  score  : {score}/100  ({label})")

    (out / "score.json").write_text(json.dumps({**m, "score": score, "verdict": label},
                                               indent=2), encoding="utf-8")

    who = name or "yeh site"
    subject = who.capitalize() + (f", {city}" if city else "")
    worst = worst_metric(m)
    hook = hook_for(m, score, label, subject)

    other_fixes = [
        "Booking button first screen pe, ek hi, bada.",
        "Mobile pe font 16px se chhota mat rakh.",
        "Har image pe width aur height likh, layout jump band.",
    ]
    other_fixes = [f for f in other_fixes if f != worst["fix"]][:2]
    fixes = [worst["fix"], *other_fixes]

    scenes = [
        {
            "kind": "hook", "pill": hook["pill"], "bar": "0xA31C1B",
            "bg": {"shot": True, "dim": 1.0, "blur": 0.0},
            "blocks": hook["blocks"],
            "voice": hook["voice"],
        },
        {
            "kind": "evidence", "pill": "EVIDENCE", "bar": "0xA31C1B",
            "bg": {"shot": True, "dim": 0.55, "blur": 7.0},
            "blocks": [("accent", "Yeh guess nahi hai."),
                       ("hud", [("SERVER RESPONSE", f"{m['ttfb_s']} s"),
                                ("PAGE WEIGHT", f"{m['weight_kb']} KB"),
                                ("REQUESTS", str(m["requests"])),
                                ("BIGGEST FILE", f"{m['biggest_kb']} KB"),
                                ("MEASURED", time.strftime("%d %b %Y"))])],
            "voice": f"Paanch baar measure kiya. Server {m['ttfb_s']} second, "
                     f"page {m['weight_kb']} kilobyte, {m['requests']} requests, "
                     f"sabse badi file {m['biggest_kb']} kilobyte.",
        },
        {
            "kind": "fixes", "pill": "EDUCATION", "bar": "0xA31C1B",
            "bg": {"shot": True, "dim": 0.70, "blur": 3.0},
            "blocks": [("accent", "Teen fixes, free mein."),
                       ("list", fixes)],
            "voice": ("Teen fixes, free mein. "
                      f"Pehla: {fixes[0]} Doosra: {fixes[1]} Teesra: {fixes[2]}"),
        },
        {
            "kind": "score", "pill": "", "bar": "0xA31C1B",
            "bg": {"shot": False},
            "blocks": [("score", (score, f"FLOW SCORE - {label}", note))],
            "voice": f"Flow Score {score}. {note}",
        },
        {
            "kind": "cta", "pill": "", "bar": "0xF2F0EC",
            "bg": {"shot": False, "accent": True, "site_line": True},
            "blocks": [("big", "Comment SCORE."),
                       ("body", "Teri site ka Flow Score bhejta hoon. Free. Public.")],
            "voice": "Comment SCORE. Teri site ka Flow Score bhejta hoon. Free, aur public.",
        },
    ]

    total = len(scenes)
    do_video = not skip_video
    clips: list[Path] = []
    durs: list[float] = []
    voice_cfg = cf.voice_sequence(1)[0]

    domain = urllib.parse.urlparse(m["final_url"]).netloc.replace("www.", "")

    for i, sc in enumerate(scenes):
        bg = out / f"bg-{i + 1}.png"
        tx = out / f"tx-{i + 1}.png"

        opts = sc["bg"]
        stage(bg, i, total, sc["pill"],
              shot=shot_path if opts.get("shot") else None,
              label=domain,
              dim=opts.get("dim", 1.0),
              blur=opts.get("blur", 0.0),
              crop=opts.get("crop"),
              accent=opts.get("accent", False),
              site_line=opts.get("site_line", False))

        band = BAND_WINDOW if opts.get("shot") else None
        text_layer(tx, sc["blocks"], on_accent=opts.get("accent", False), band=band)

        if not do_video:
            durs.append(cf.estimate(sc["voice"]))
            continue

        mp3 = out / f"scene-{i + 1}.mp3"
        mp4 = out / f"scene-{i + 1}.mp4"
        rec = out / f"scene-{i + 1}.wav"

        if rec.exists():
            # Drop-in real voice: record scene-N.wav yourself and it wins over TTS.
            audio = rec
        else:
            voicepipe.speak(sc["voice"], mp3, voice_cfg["voice"],
                            voice_cfg["rate"], voice_cfg["pitch"], seed=1000 + i)
            audio = mp3

        dur = max(voicepipe.probe(audio) + 0.45, 3.0)
        durs.append(dur)
        cf.scene_clip(bg, tx, audio, dur, mp4, sc["bar"])
        clips.append(mp4)
        print(f"    scene {i + 1}/{total}  {dur:.1f}s{'  (recorded)' if rec.exists() else ''}")

    if do_video:
        cf.concat_clips(clips, out / "video.mp4")
        cf.write_srt([{"voice": s["voice"]} for s in scenes], durs, out / "video.srt")
        cover = Image.alpha_composite(
            Image.open(out / "bg-1.png").convert("RGBA"),
            Image.open(out / "tx-1.png").convert("RGBA"),
        )
        cover.convert("RGB").save(out / "video-cover.jpg", quality=92)
        for p in (list(out.glob("scene-*.mp4")) + list(out.glob("scene-*.mp3"))
                  + list(out.glob("bg-*.png")) + list(out.glob("tx-*.png"))):
            p.unlink(missing_ok=True)
        (out / "concat.txt").unlink(missing_ok=True)

    # script
    t = 0.0
    rows = []
    for i, (sc, dur) in enumerate(zip(scenes, durs), 1):
        rows.append(f"### Scene {i} - {sc['kind']} ({cf.fmt_time(t)} - {cf.fmt_time(t + dur)})\n"
                    f"**Voiceover**\n\n> {sc['voice']}\n")
        t += dur

    (out / "script.md").write_text(
        f"# Autopsy - {who}\n\n"
        f"**URL:** {m['final_url']}  \n"
        f"**Server response:** {m['ttfb_s']}s (best of 5)  \n"
        f"**Page weight:** {m['weight_kb']} KB  \n"
        f"**Requests:** {m['requests']}  \n"
        f"**Biggest file:** {m['biggest_name']} ({m['biggest_kb']} KB)  \n"
        f"**Flow Score:** {score}/100 ({label})  \n"
        f"**Runtime:** {cf.fmt_time(t)}  \n"
        f"**Voice:** {voice_cfg['voice']}\n\n" + "\n".join(rows),
        encoding="utf-8",
    )

    site = cf.CONFIG.get("website", "")
    opener = (f"{subject} ne {score}/100 score kiya."
              if score >= 70 else
              f"{subject} ka Flow Score sirf {score}/100 hai.")
    lead = ("Sabse heavy cheez" if score >= 70 else "Sabse bada leak")
    caption = (
        f"{opener}\n"
        f"{lead}: {worst['short']}.\n\n"
        f"Yeh guess nahi, measurement hai (best of 5):\n"
        f"- server response: {m['ttfb_s']}s\n"
        f"- page weight: {m['weight_kb']} KB\n"
        f"- requests: {m['requests']}\n"
        f"- sabse badi file: {m['biggest_name']} ({m['biggest_kb']} KB)\n\n"
        f"Verdict: {label}. {note}\n\n"
        f"Comment SCORE aur main teri site ka free score bhejta hoon.\n\n"
        f"Site: {site}"
    )
    (out / "caption.txt").write_text(caption, encoding="utf-8")
    (out / "hashtags.txt").write_text(
        "#websitespeed #localbusiness #smallbusinessindia #webdesign #flowlabs\n\n"
        "Search keywords: website speed test, website audit india, flow score",
        encoding="utf-8",
    )

    print(f"\nDone -> {out}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=False, help="site to autopsy")
    ap.add_argument("--name", default="", help="business name (leave blank to stay generic)")
    ap.add_argument("--city", default="", help="e.g. Pune")
    ap.add_argument("--shot", default=None, help="use an existing screenshot instead of capturing")
    ap.add_argument("--skip-video", action="store_true")
    args = ap.parse_args()

    if not args.url and not args.shot:
        ap.error("pass --url or --shot")

    url = args.url or "https://example.com"
    build(url, args.name, args.city,
          Path(args.shot) if args.shot else None, args.skip_video)
    return 0


if __name__ == "__main__":
    sys.exit(main())
