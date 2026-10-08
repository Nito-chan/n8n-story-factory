# Story Factory — Complete Setup Guide

## Overview

Fully automated revenge-story YouTube pipeline. Once configured, it will:
1. Fetch top stories from Reddit
2. Pick one at random
3. Generate a YouTube script via Gemini (Google One subscription)
4. Generate 10-12 cinematic scene images via Gemini/NanoBanana
5. Generate professional narration via Fish Audio (free tier)
6. Assemble everything into an MP4 video via FFmpeg
7. Log everything to `output/production_log.json`

Zero cost. Runs from a single Python script. No server needed.

## Prerequisites

| Item | How to get it |
|------|---------------|
| Gemini API key | [aistudio.google.com](https://aistudio.google.com) → API keys (free with Google One) |
| Fish Audio API key | [fish.audio](https://fish.audio) → Dashboard → API |
| FFmpeg | Already bundled with CapCut at `C:\Users\tanji\AppData\Local\CapCut\Apps\8.7.0.3706\ffmpeg.exe` |
| Python 3.14 | Already installed (`python --version`) |

## Setup

### 1. Set your API keys

Edit the `.env` file in this directory (rename from `.env.template` if needed):

```
GEMINI_API_KEY=your-key-here
FISH_AUDIO_KEY=your-key-here
```

### 2. Run the pipeline

Double-click `start.cmd` (one-click run) or run from terminal:

```
cd C:\Users\tanji\Opencode\n8n_setup
python orchestrator.py
```

### 3. Find your video

Completed videos are saved to `output\*.mp4`.

## Scheduling (Daily Automation)

### Option A: Windows Task Scheduler (recommended)

1. Press `Win+R`, type `taskschd.msc`
2. Click **Create Task**
3. **General** tab: Name = "Story Factory", check "Run whether user is logged on or not"
4. **Triggers** tab: New → Daily → Start at 8:00 AM → OK
5. **Actions** tab: New →
     - Action: Start a program
     - Program/script: `C:\Users\tanji\Opencode\n8n_setup\start.cmd`
6. OK

### Option B: Use the XML (advanced)

```
schtasks /create /xml schedule.xml /tn "Story Factory"
```

## Troubleshooting

| Error | Fix |
|-------|-----|
| `GEMINI_API_KEY not set` | Edit `.env` and add your key |
| `Failed to parse Gemini response` | Run again — Gemini output varies |
| `No stories with text found on Reddit` | Reddit may be rate-limiting; wait and retry |
| `Video assembly failed` | Check that FFmpeg is accessible and scene images exist |
| Fish Audio 401 | Check your Fish Audio API key in `.env` |

## What's Next

- **YouTube Upload** — Add YouTube Data API v3 upload in a follow-up script
- **Background Music** — Overlay Audio Library tracks during assembly
- **Thumbnail Generation** — Extract frame from scene 1 with text overlay
- **Google Sheets Log** — Replace local JSON logging with a Google Sheet
