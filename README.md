# Flow Labs Content Factory

One command generates ready-to-post social content for **The Flow Labs** —
websites, AI and automation. Hinglish, roast tone, real videos, no cameras.

Two generators:

| Generator | What it makes | Command |
|---|---|---|
| 3-day pack | 3 animated reels + captions, carousels, Threads + LinkedIn posts, stories, posting plan | `GENERATE.bat` |
| Site Autopsy | a teardown reel of a real website, with a real measured score | `AUTOPSY.bat --url <site>` |

Everything runs offline on your machine except text-to-speech, which uses
Microsoft's public edge-tts endpoint.

---

## 1. Build it (first time, ~10 minutes)

### Step 1 - Install Python 3.11 or newer

https://www.python.org/downloads/windows/

During the installer, tick **Add python.exe to PATH**. Anything 3.11+ works.

Verify:

```powershell
python --version
```

### Step 2 - Install ffmpeg

It is what renders the videos. Pick one:

```powershell
winget install Gyan.FFmpeg
```

or download a release from https://www.gyan.dev/ffmpeg/builds/ and add its `bin`
folder to your PATH.

Then open a **new** terminal and verify:

```powershell
ffmpeg -version
```

If this fails, the videos will not render. Everything else still does.

### Step 3 - Clone this repo and install the Python packages

```powershell
git clone https://github.com/fresherscomputersc-hash/content.git
cd content\tools\content-factory
pip install -r requirements.txt
```

### Step 4 - Pick your voice (optional, recommended)

Eight samples are already rendered in `voice-samples/`. Open the mp3s, pick
your two favourites, then run the sampler or just edit `config.json`.

```powershell
python voice-test.py
```

Defaults are already good:

- `en-IN-NeerjaExpressiveNeural` - 60% of lines
- `en-IN-PrabhatNeural` - 40% of lines

### Step 5 - Generate your first pack

```powershell
:: from the repo root
GENERATE.bat
```

Output lands in `content\YYYY-MM-DD\`. Render takes 3-5 minutes for 3 videos.

---

## 2. Repo layout

```
content/                 <- generated posts land here (git-ignored)
assets/
  work-*.png             <- reel backgrounds, blurred
tools/content-factory/
  run.py                 <- 3-day pack generator (main file)
  autopsy.py             <- Site Autopsy generator
  voice.py               <- voice pipeline (TTS, mastering)
  voice-test.py          <- voice sampler
  config.json            <- brand, voices, colours, posting times
  content_bank.json      <- 15 content angles you can edit
  run.bat  /  autopsy.bat
GENERATE.bat             <- repo-root shortcut for run.bat
AUTOPSY.bat              <- repo-root shortcut for autopsy.bat
```

---

## 3. What the 3-day pack contains

For each day, in `content\YYYY-MM-DD\day-N\`:

| File | What it is |
|---|---|
| `video.mp4` | 9:16 reel, 1080x1920, voiceover + animated text |
| `video.srt` | subtitles |
| `video-cover.jpg` | cover image |
| `script.md` | scene-by-scene script with timecodes |
| `caption.txt` | Instagram caption, website included |
| `hashtags.txt` | put this in the first comment |

Plus, one level up:

- `START-HERE.md` - exact posting order, times, checklist
- `plan.md` - strategy, content mix, voice split
- `captions.md` - every caption in one place
- `calendar.csv` - importable schedule
- `carousel.md`, `threads.txt`, `linkedin.txt`, `stories.txt`
- `VIRAL-PLAYBOOK.md` - hooks, keywords, hashtag rule, first 60 minutes

### The mix stays on-brand by construction

Every video is the same five beats, so the mix is exact, not approximate:

| Beat | Category |
|---|---|
| hook | other |
| problem | education |
| three fixes | education |
| proof | case study |
| CTA | other |

= **40% education / 20% case study / 40% other, inside every video.**

### What the videos do

- text slides up 34px and fades in
- background slowly zooms 1.00 -> 1.10
- progress bar fills in accent red
- film grain + vignette
- hard cuts between scenes (better retention than dips to black)

---

## 4. Site Autopsy - the format competitors cannot copy

```powershell
:: from the repo root
AUTOPSY.bat --url https://client-site.com --name "Sharma Dental" --city Pune
AUTOPSY.bat --url https://client-site.com --skip-video    :: plan + copy only
```

It opens the real site in a headless Chrome, captures it into a browser window
frame, measures it, and scores it.

Measured live, every run:

| Metric | Method |
|---|---|
| Server response | best of 5 warm requests |
| Page weight | HTML + every linked asset |
| Requests | distinct linked assets |
| Biggest file | largest single asset |

### Flow Score

0-100, weighted: server response 30, page weight 25, request count 20,
biggest file 25. Coarse bands, total rounded to 5, so a published score does
not swing 10 points between two runs.

| Score | Verdict | Hook |
|---|---|---|
| 70-100 | HEALTHY | credibility - "aaj roast nahi, aaj proof" |
| 40-69 | NEEDS SURGERY | names the single weakest metric |
| 0-39 | EMERGENCY | full roast |

The hook, the three fixes and the caption are all derived from the
measurements, so a healthy site never gets roasted for being slow.

Output lands in `content\autopsy-<name>\`:
`video.mp4`, `video.srt`, `video-cover.jpg`, `script.md`, `caption.txt`,
`hashtags.txt`, `score.json`, `site.png`.

Requires Chrome or Edge installed (it is used for the screenshot).

### Drop in your own voice

Record a `scene-1.wav` ... `scene-5.wav` into that output folder and re-run -
your recording wins over TTS automatically.

---

## 5. Change the content

### `config.json`

```json
{
  "brand": "The Flow Labs",
  "handle": "@the.flow.labs",
  "website": "https://the-flow-labs.vercel.app",
  "tone": "roast, meme, playful",
  "voice_mix": [
    { "voice": "en-IN-NeerjaExpressiveNeural", "weight": 0.6, "rate": "+22%", "pitch": "+3Hz" },
    { "voice": "en-IN-PrabhatNeural",          "weight": 0.4, "rate": "+24%", "pitch": "+4Hz" }
  ],
  "category_mix": { "education": 0.4, "case_study": 0.2, "other": 0.4 },
  "colors": { "accent": "#A31c1b", "text": "#f2f0ec", "bg": "#030302" }
}
```

- `handle` and `website` appear on the CTA card of every video
- `voice_mix` weights track the ratio rather than clustering

### `content_bank.json`

Fifteen Hinglish angles. Each one:

```json
{
  "theme": "Mobile site",
  "category": "education",
  "keywords": ["mobile website", "responsive design"],
  "hook": "...",
  "problem": "...",
  "fixes": ["...", "...", "..."],
  "proof": "...",
  "cta": "...",
  "tags": ["..."]
}
```

Angles rotate by date, so every run produces different content. Add your own
object to the array and it enters the rotation automatically.

---

## 6. Team workflow

- Do **not** commit `content/` - it is git-ignored. Videos are outputs, not source.
- To change branding, editing, voice mix, or angles: edit
  `tools/content-factory/config.json` / `content_bank.json`, then open a PR.
- Keep `README.md` accurate. If you change how a command works, update it in
  the same PR.
- Never commit API keys, client names, or client data.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ffmpeg` not found | ffmpeg is not on PATH. Close the terminal and reopen after installing. |
| `getaddrinfo failed` during TTS | network blip reaching Microsoft. It retries 6 times automatically; re-run if it still fails. |
| Videos look wrong, text overflows | you edited `screen` copy too long. Keep hooks under ~12 words. |
| No videos, only text files | you used `--skip-video`, or ffmpeg is missing. |
| `Chrome or Edge not found` | Site Autopsy needs Chrome or Edge installed for the headless screenshot. |
| Fonts error | the generator needs a system font set. On Windows it uses Segoe UI; other platforms fall back automatically. |

---

## 8. Ethics

Do not publish a named business scoring badly without permission. Either get
consent, or blur the logo and say "ek client site". Unpublished scores are
worth more as an outreach opener than as a public post.
