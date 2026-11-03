#!/usr/bin/env python3
"""
Voice sampler for Flow Labs.

Renders the same playful line in several voices so you can pick one by ear.

    python voice-test.py

Output: voice-samples/*.mp3 + voice-samples/README.md
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

HERE = Path(__file__).resolve().parent
OUT = HERE / "voice-samples"

LINE = (
    "Bhai, your website is slower than a Monday morning. "
    "Customers gave up, ordered from the competition, and put it on their story. "
    "Fix the site. Keep the chai."
)

VOICES = [
    {
        "id": "en-IN-NeerjaExpressiveNeural",
        "label": "Neerja Expressive (Indian English, female)",
        "rate": "+14%",
        "pitch": "+3Hz",
        "why": "Closest to Hinglish creator energy. Expressive without sounding like a newsreader.",
    },
    {
        "id": "en-IN-PrabhatNeural",
        "label": "Prabhat (Indian English, male)",
        "rate": "+16%",
        "pitch": "+4Hz",
        "why": "The 'bhai next door' voice. Good if you want the reel to feel like a friend talking.",
    },
    {
        "id": "en-US-EmmaNeural",
        "label": "Emma (US, female)",
        "rate": "+14%",
        "pitch": "+2Hz",
        "why": "Cheerful and clear. Safest playful option for a global audience.",
    },
    {
        "id": "en-US-RogerNeural",
        "label": "Roger (US, male)",
        "rate": "+10%",
        "pitch": "+2Hz",
        "why": "Lively storyteller. Works for teardown and 'let me tell you what happened' reels.",
    },
    {
        "id": "en-US-GuyNeural",
        "label": "Guy (US, male)",
        "rate": "+8%",
        "pitch": "+3Hz",
        "why": "Hype-man energy. Good for offer and launch posts, too much for every day.",
    },
    {
        "id": "en-US-BrianNeural",
        "label": "Brian (US, male)",
        "rate": "+12%",
        "pitch": "+1Hz",
        "why": "Casual and approachable. Reads like a founder, not an ad.",
    },
    {
        "id": "en-AU-NatashaNeural",
        "label": "Natasha (Australian, female)",
        "rate": "+12%",
        "pitch": "+2Hz",
        "why": "Warm and a little cheeky. Different enough to stand out in an Indian feed.",
    },
    {
        "id": "en-US-AnaNeural",
        "label": "Ana (US, female, cartoon)",
        "rate": "+0%",
        "pitch": "+0Hz",
        "why": "Full meme energy. Use once in ten posts, never for client work.",
    },
]


async def render(voice: dict, out: Path) -> None:
    comm = edge_tts.Communicate(
        LINE,
        voice["id"],
        rate=voice["rate"],
        pitch=voice["pitch"],
    )
    await comm.save(str(out))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []

    for i, v in enumerate(VOICES, 1):
        name = f"{i:02d}-{v['id'].replace('Neural', '').lower()}.mp3"
        path = OUT / name
        asyncio.run(render(v, path))
        size = path.stat().st_size // 1024
        rows.append((i, v, name, size))
        print(f"  {i}/{len(VOICES)}  {v['label']}  ({size} KB)")

    lines = [
        "# Voice samples",
        "",
        "Same script, different voices. Open the mp3s and pick one.",
        "",
        "**Script used:**",
        "",
        f"> {LINE}",
        "",
        "| # | Voice | Rate | Pitch | File | Why |",
        "|---|---|---|---|---|---|",
    ]
    for i, v, name, _ in rows:
        lines.append(
            f"| {i} | {v['label']} | {v['rate']} | {v['pitch']} | `{name}` | {v['why']} |"
        )

    lines += [
        "",
        "## How to apply the winner",
        "",
        "Open `config.json` and set:",
        "",
        "```json",
        '{',
        f'  "voice": "{VOICES[0]["id"]}",',
        f'  "voice_rate": "{VOICES[0]["rate"]}",',
        f'  "voice_pitch": "{VOICES[0]["pitch"]}"',
        "}",
        "```",
        "",
        "Or override per run:",
        "",
        "```bash",
        f'python run.py --voice {VOICES[0]["id"]} --rate +14% --pitch +3Hz',
        "```",
        "",
        "## Note on tone",
        "",
        "A voice can only carry so much. Playful comes from three things together:",
        "",
        "1. the voice (this test),",
        "2. the script (short sentences, one joke, no corporate words),",
        "3. the edit (cut the pause after the punchline, keep it under 35 seconds).",
        "",
        "If the script is stiff, the funniest voice will still sound like a call centre.",
    ]

    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone. Open {OUT / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
