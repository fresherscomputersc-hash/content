# Content Factory

One command. Three days of Hinglish social content, with animated videos.

## Run it

Double-click `run.bat`, or:

```bash
python run.py
```

Output lands in `../../content/YYYY-MM-DD/`.

## What it makes

| File | What it is |
|---|---|
| `START-HERE.md` | posting order, times, exact steps, checklist |
| `VIRAL-PLAYBOOK.md` | hooks, keywords, hashtag rule, first-60-minutes plan |
| `plan.md` | 3-day strategy, 40/20/40 mix, voice split, targets |
| `calendar.csv` | importable schedule |
| `captions.md` | every caption in one place |
| `day-N/video.mp4` | 9:16 reel, 1080x1920, voiceover + animated text |
| `day-N/video.srt` | subtitles |
| `day-N/video-cover.jpg` | cover image |
| `day-N/script.md` | scene-by-scene script, beat category, timecodes |
| `day-N/caption.txt` | Instagram caption (website included) |
| `day-N/hashtags.txt` | first comment: hashtags + search keywords |
| `day-N/threads.txt` | Threads post |
| `day-N/linkedin.txt` | LinkedIn post |
| `day-N/carousel.md` | 7-slide carousel |
| `day-N/stories.txt` | 2 story prompts |

## What the video does

Five beats, same order every time:

| Beat | Pill on screen | Category |
|---|---|---|
| 1. Roast hook | ROAST | other |
| 2. Why it happens | EDUCATION | education |
| 3. Three fixes | EDUCATION | education |
| 4. Proof | CASE STUDY | case study |
| 5. CTA | (closing) | other |

That is 2 education, 1 case study, 2 other = **40/20/40 inside every video**.

Motion and polish, per scene:

- text layer slides up 34px and fades in over 0.5s
- background slowly zooms 1.00 -> 1.10 across the scene
- top progress bar fills in accent red (white on the CTA card)
- film grain + vignette on the background, text stays crisp
- hard cuts between scenes (no dip to black - better retention)

## Options

```bash
python run.py --days 3
python run.py --days 5               # 5-day pack hits 60/40 and 40/20/40 exactly
python run.py --start 2026-11-05
python run.py --skip-video           # plan + copy only, no rendering
python run.py --seed 42              # force a different angle rotation
python run.py --voice en-IN-PrabhatNeural --rate +22% --pitch +4Hz
```

---

# Site Autopsy

The generic text-card reel is a commodity - anyone with a prompt can make one.
Site Autopsy is not: it captures the *real* site in a real browser, measures it,
and scores it. The evidence is the format, and evidence cannot be prompted.

```bash
python autopsy.py --url https://client-site.com
python autopsy.py --url https://client-site.com --name "Sharma Dental" --city Pune
python autopsy.py --url https://client-site.com --skip-video
python autopsy.py --shot site.png --url https://x.com    # use your own screenshot
```

Or double-click `AUTOPSY.bat` in the project root.

Output lands in `../../content/autopsy-<slug>/`.

## What it measures

Every number is real, measured live from the machine that runs it:

| Metric | How |
|---|---|
| Server response | best of 5 warm requests (the warm-up hit is discarded) |
| Page weight | HTML + every linked asset |
| Requests | count of distinct linked assets |
| Biggest file | largest single asset, by name |
| Measured | date stamp, printed on the EVIDENCE scene |

## Flow Score

0-100, weighted: server response 30, page weight 25, request count 20, biggest file 25.
Each metric uses coarse bands, not a continuous curve, and the total is rounded to 5.
A published score that swings 10 points between two runs is worthless, so the bands
absorb measurement noise.

| Score | Verdict | Hook style |
|---|---|---|
| 70-100 | HEALTHY | credibility - "aaj roast nahi, aaj proof" |
| 40-69 | NEEDS SURGERY | names the single worst metric |
| 0-39 | EMERGENCY | full roast |

The hook, the three fixes and the caption are all chosen from the measurements, so a
healthy site never gets roasted for being slow. The first fix always targets the
weakest metric.

## The five scenes

| Scene | Pill | Visual |
|---|---|---|
| 1. Hook | PROOF / ROAST / EMERGENCY | real browser window, domain in the URL bar |
| 2. Evidence | EVIDENCE | same window, blurred, with a five-row HUD |
| 3. Fixes | EDUCATION | window blurred back, three numbered fixes |
| 4. Score | (none) | 0-100 ring, verdict line |
| 5. CTA | (none) | "Comment SCORE", website + handle |

## Ethics

Do not publish a named business getting a bad score without permission. Either get
consent, or blur the logo and say "ek client site" instead of naming them. Use the
unpublished score as the outreach opener - that is where it is worth the most.

## Requirements

- Python 3.11+
- `pip install edge-tts pillow`
- `ffmpeg` on PATH
- Chrome or Edge installed (headless screenshot capture)

## Change the content

- `config.json` - brand, handle, website, voices, category mix, posting times, colours
- `content_bank.json` - 15 Hinglish angles. Each has `category`, `theme`, `hook`, `problem`, three `fixes`, `proof`, `cta`, `tags`, `keywords`.

The script rotates by date, so every run is different. Add your own angle to the array and it enters rotation automatically.

### The two mixes

`config.json`:

```json
"voice_mix": [
  { "voice": "en-IN-NeerjaExpressiveNeural", "weight": 0.6, "rate": "+22%", "pitch": "+3Hz" },
  { "voice": "en-IN-PrabhatNeural",          "weight": 0.4, "rate": "+24%", "pitch": "+4Hz" }
],
"category_mix": { "education": 0.4, "case_study": 0.2, "other": 0.4 }
```

Both use the same weighted-sequence algorithm, so the running counts track the weights
instead of clustering. A 3-day pack gives Neerja, Prabhat, Neerja; a 5-day pack gives
3/2 on voices and 2/1/2 on categories.

## Change the voice

Run the sampler first:

```bash
python voice-test.py
```

It renders the same playful line in 8 voices into `voice-samples/`. Open the mp3s, pick one, then set it in `config.json`:

| Voice | Use |
|---|---|
| `en-IN-NeerjaExpressiveNeural` | Indian English, female, expressive (default, 60%) |
| `en-IN-PrabhatNeural` | Indian English, male, "bhai next door" (default, 40%) |
| `en-IN-NeerjaNeural` | Indian English, female, neutral |
| `en-US-EmmaNeural` | US, female, cheerful |
| `en-US-RogerNeural` | US, male, lively storyteller |
| `en-US-BrianNeural` | US, male, casual founder |
| `en-AU-NatashaNeural` | Australian, female, warm and cheeky |
| `en-US-AnaNeural` | Cartoon energy, use sparingly |

## Notes

- Videos use your `assets/*.png` work screenshots as a blurred background.
- Rendering 3 videos takes roughly 3-5 minutes.
- If TTS fails, it retries 6 times with backoff (edge-tts calls Microsoft servers).
- Reels are faceless by design: text cards + voiceover. No camera needed.
- The website on the CTA card comes from `website` in `config.json`.

## About the voice

`voice.py` splits each script into sentences, renders each one with a small rate and
pitch jitter, trims the ~0.8s of silence edge-tts pads onto every clip, joins them with
a 180ms gap, then runs a mastering chain (highpass, presence EQ, 2.8:1 compression,
limiter, -16 LUFS loudness).

That removes the main "AI" tells: identical prosody on every sentence and dead air
between them. It does **not** make the voice human. edge-tts has no emotion control, so
there is a ceiling. If the voice still bothers you after this, the honest options are:

1. **Record it yourself.** Cheapest, most human, and it becomes your brand voice.
   Drop a recorded `voice.wav` per scene and skip `voicepipe.speak()` in `autopsy.py`.
2. **Pay for a TTS with emotion tags** (ElevenLabs and similar). Not free.
3. **Lean into it.** A measured, deadpan delivery over real data is a legitimate style.
   It reads as "audit", not "influencer" - which is the point of Site Autopsy.
