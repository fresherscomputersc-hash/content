# Voice samples

Same script, different voices. Open the mp3s and pick one.

**Script used:**

> Bhai, your website is slower than a Monday morning. Customers gave up, ordered from the competition, and put it on their story. Fix the site. Keep the chai.

| # | Voice | Rate | Pitch | File | Why |
|---|---|---|---|---|---|
| 1 | Neerja Expressive (Indian English, female) | +14% | +3Hz | `01-en-in-neerjaexpressive.mp3` | Closest to Hinglish creator energy. Expressive without sounding like a newsreader. |
| 2 | Prabhat (Indian English, male) | +16% | +4Hz | `02-en-in-prabhat.mp3` | The 'bhai next door' voice. Good if you want the reel to feel like a friend talking. |
| 3 | Emma (US, female) | +14% | +2Hz | `03-en-us-emma.mp3` | Cheerful and clear. Safest playful option for a global audience. |
| 4 | Roger (US, male) | +10% | +2Hz | `04-en-us-roger.mp3` | Lively storyteller. Works for teardown and 'let me tell you what happened' reels. |
| 5 | Guy (US, male) | +8% | +3Hz | `05-en-us-guy.mp3` | Hype-man energy. Good for offer and launch posts, too much for every day. |
| 6 | Brian (US, male) | +12% | +1Hz | `06-en-us-brian.mp3` | Casual and approachable. Reads like a founder, not an ad. |
| 7 | Natasha (Australian, female) | +12% | +2Hz | `07-en-au-natasha.mp3` | Warm and a little cheeky. Different enough to stand out in an Indian feed. |
| 8 | Ana (US, female, cartoon) | +0% | +0Hz | `08-en-us-ana.mp3` | Full meme energy. Use once in ten posts, never for client work. |

## How to apply the winner

Open `config.json` and set:

```json
{
  "voice": "en-IN-NeerjaExpressiveNeural",
  "voice_rate": "+14%",
  "voice_pitch": "+3Hz"
}
```

Or override per run:

```bash
python run.py --voice en-IN-NeerjaExpressiveNeural --rate +14% --pitch +3Hz
```

## Note on tone

A voice can only carry so much. Playful comes from three things together:

1. the voice (this test),
2. the script (short sentences, one joke, no corporate words),
3. the edit (cut the pause after the punchline, keep it under 35 seconds).

If the script is stiff, the funniest voice will still sound like a call centre.