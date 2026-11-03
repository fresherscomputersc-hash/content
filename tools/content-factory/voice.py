"""
Voice pipeline for Flow Labs.

edge-tts alone sounds like a screen reader because every sentence is rendered with
identical prosody. This module:

  1. splits a script into sentences,
  2. renders each sentence with a slightly different rate and pitch,
  3. joins them with natural gaps,
  4. runs a mastering chain (highpass, presence EQ, compression, limiter, loudnorm).

That does not make it human. It makes it *less uniform*, which is the part that
reads as "AI". If you want actually human, record it yourself - see README.
"""

from __future__ import annotations

import asyncio
import random
import re
import subprocess
import time
import wave
from pathlib import Path

import edge_tts

SR = 24000


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _parse_rate(v: str) -> int:
    m = re.match(r"([+-]?)(\d+)%", v.strip())
    if not m:
        return 14
    n = int(m.group(2))
    return -n if m.group(1) == "-" else n


def _parse_pitch(v: str) -> int:
    m = re.match(r"([+-]?)(\d+)Hz", v.strip(), re.I)
    if not m:
        return 0
    n = int(m.group(2))
    return -n if m.group(1) == "-" else n


def _split(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    out = [p.strip() for p in parts if p.strip()]
    return out or [text.strip()]


def _ffmpeg(args: list[str]) -> None:
    p = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-800:]}")


def _wav_frames(path: Path) -> bytes:
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SR or w.getnchannels() != 1:
            raise RuntimeError(f"unexpected wav format in {path}")
        return w.readframes(w.getnframes())


# --------------------------------------------------------------------------
# synthesis
# --------------------------------------------------------------------------

async def _one(text: str, voice: str, rate: str, pitch: str, out: Path) -> None:
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(str(out))


def _synth_sentence(text: str, voice: str, rate: str, pitch: str,
                    out: Path, rng: random.Random) -> None:
    """Render one sentence, with a small prosody jitter so the delivery varies."""
    r = _parse_rate(rate) + rng.choice([-3, -2, 0, 0, 2, 3])
    p = _parse_pitch(pitch) + rng.choice([-6, -4, -2, 0, 0, 2, 4, 6])
    r = max(-20, min(40, r))
    p = max(-20, min(20, p))

    for attempt in range(6):
        try:
            asyncio.run(_one(text, voice, f"{r:+d}%", f"{p:+d}Hz", out))
            if out.exists() and out.stat().st_size > 800:
                return
        except Exception:  # noqa: BLE001
            time.sleep(min(2 + attempt * 2, 10))
    raise RuntimeError(f"TTS failed for: {text[:60]}")


def speak(text: str, out: Path, voice: str, rate: str = "+14%",
          pitch: str = "+0Hz", seed: int = 0) -> None:
    """Render `text` with varied prosody, join it, master it, write `out`."""
    rng = random.Random(seed or hash(text) & 0xFFFF)
    tmp = out.parent / f".{out.stem}-parts"
    tmp.mkdir(parents=True, exist_ok=True)

    sentences = _split(text)
    wavs: list[Path] = []

    for i, s in enumerate(sentences):
        mp3 = tmp / f"s{i}.mp3"
        wav = tmp / f"s{i}.wav"
        _synth_sentence(s, voice, rate, pitch, mp3, rng)
        # edge-tts pads roughly 0.8s of silence onto every clip. Stack four of
        # those and the delivery drags. Trim head and tail, then add our own gap.
        _ffmpeg([
            "-i", str(mp3),
            "-af", ("silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,"
                    "areverse,"
                    "silenceremove=start_periods=1:start_duration=0:start_threshold=-45dB,"
                    "areverse"),
            "-ar", str(SR), "-ac", "1", str(wav),
        ])
        wavs.append(wav)

    gap = int(SR * 0.18)
    silence = b"\x00\x00" * gap

    joined = tmp / "joined.wav"
    with wave.open(str(joined), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        for i, path in enumerate(wavs):
            w.writeframes(_wav_frames(path))
            if i != len(wavs) - 1:
                w.writeframes(silence)

    master = (
        "highpass=f=95,"
        "equalizer=f=220:t=q:w=1.0:g=-2,"
        "equalizer=f=3200:t=q:w=1.2:g=2.5,"
        "acompressor=threshold=-20dB:ratio=2.8:attack=6:release=140:makeup=2,"
        "alimiter=limit=0.94,"
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    )
    _ffmpeg(["-i", str(joined), "-af", master, "-ar", str(SR), "-ac", "1",
             "-c:a", "libmp3lame", "-q:a", "3", str(out)])

    for p in tmp.glob("*"):
        p.unlink(missing_ok=True)
    tmp.rmdir()


def probe(path: Path) -> float:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(p.stdout.strip())


if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else (
        "Bhai, teri website 9 second leti hai. Customer 3 second deta hai. "
        "Koi guess nahi, measurement hai."
    )
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("voice-demo.mp3")
    speak(text, out, "en-IN-NeerjaExpressiveNeural", "+14%", "+3Hz")
    print(f"wrote {out}  ({probe(out):.2f}s)")
