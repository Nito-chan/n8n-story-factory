#!/usr/bin/env python3
"""Story Factory — Full Auto Pipeline
Zero-cost stack: Groq (text) + Pollinations.ai (images) + edge-tts (voice).

Usage:
    set GROQ_API_KEY=gsk_your_key
    python orchestrator.py

Or use a .env file.
"""

import asyncio
import io
import json
import os
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
LOG_FILE = os.path.join(OUTPUT_DIR, "production_log.json")


def log(msg: str, level: str = "info") -> None:
    ts = time.strftime("%H:%M:%S")
    marks = {"info": " ", "ok": " ", "warn": " ", "err": " ", "step": ">"}
    print(f"  {ts} {marks.get(level, ' ')} {msg}")
    sys.stdout.flush()


def load_env() -> dict:
    env_path = os.path.join(BASE_DIR, ".env")
    keys = {}
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    keys[k.strip()] = v.strip()
    for var in ["OPENROUTER_API_KEY", "GROQ_API_KEY"]:
        keys[var] = keys.get(var) or os.environ.get(var, "")
    return keys


def http_json(url: str, data: dict = None, headers: dict = None, timeout: int = 60) -> dict:
    if headers is None:
        headers = {}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:500]
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e


def http_binary(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:500]
        raise RuntimeError(f"HTTP {e.code} for image: {detail}") from e


# ── Step 1: Fetch stories from Reddit ──────────────────────────────

REDDIT_URL = "https://old.reddit.com/r/ProRevenge/top.json?limit=25&t=week&raw_json=1"
REDDIT_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def load_local_stories() -> list[dict]:
    stories_dir = os.path.join(BASE_DIR, "..", "scripts")
    posts = []
    for fname in sorted(os.listdir(stories_dir)):
        if fname.endswith(".txt"):
            fpath = os.path.join(stories_dir, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                title = fname.replace(".txt", "").replace("_", " ").title()
                posts.append({
                    "title": f"Local: {title}",
                    "selftext": content[:5000],
                    "url": "",
                    "subreddit": "local",
                    "ups": 0,
                    "author": "local",
                })
    return posts


def fetch_reddit_stories() -> list[dict]:
    log("Fetching Reddit stories…", "step")
    try:
        data = http_json(REDDIT_URL, headers=REDDIT_HEADERS, timeout=30)
        posts = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            text = (d.get("selftext") or "").strip()
            if child.get("kind") == "t3" and len(text) > 100:
                posts.append({
                    "title": d.get("title", ""),
                    "selftext": text[:5000],
                    "url": "https://reddit.com" + (d.get("permalink") or ""),
                    "subreddit": d.get("subreddit", ""),
                    "ups": d.get("ups", 0),
                    "author": d.get("author", ""),
                })
        if posts:
            log(f"Found {len(posts)} Reddit stories", "ok")
            return posts
    except Exception:
        log("Reddit blocked, falling back to local stories…", "warn")

    posts = load_local_stories()
    if posts:
        log(f"Using {len(posts)} local story files", "ok")
        return posts
    raise RuntimeError("No stories available (Reddit blocked and no local files)")


# ── Step 2: Pick one story ─────────────────────────────────────────

def pick_story(posts: list[dict]) -> dict:
    story = random.choice(posts)
    log(f"Picked: \"{story['title']}\" ({story['ups']} ups, r/{story['subreddit']})", "step")
    return story


# ── Step 3: Generate script via OpenRouter ─────────────────────────

OR_URL = "https://openrouter.ai/api/v1/chat/completions"
OR_MODEL = "gpt-4o-mini"

SCRIPT_PROMPT = """You are a professional scriptwriter for a faceless YouTube channel that tells revenge stories.

Given a Reddit story, create a YouTube video script in this exact JSON format:

{
  "title": "Clickbaity video title (max 60 chars)",
  "description": "SEO description with story hook and call to subscribe (max 300 chars)",
  "tags": ["revenge", "storytime", "reddit", "karma"],
  "script": "Full narration script with scene markers [SCENE 1], [SCENE 2] etc.",
  "scenes": [
    {
      "id": 1,
      "text": "Narration for this scene (50-80 words)",
      "image_prompt": "Detailed cinematic scene prompt..."
    }
  ]
}

CRITICAL RULES:
- Total script must be 1,200-1,500 words (8-10 minutes at 150 wpm)
- Generate EXACTLY 10-12 scenes (each 100-150 words, ~40 seconds per scene)
- Image prompts must be: cinematic, photorealistic, describe lighting, camera angle, mood, composition
- Start with a hook scene, end with a call to subscribe + moral reflection
- Keep the raw emotional tone but expand with sensory details, background, buildup
- Title must be clickable but not misleading
- Each scene text must be a complete narrative beat that can standalone visually
- Return ONLY valid JSON, no markdown wrapping

Story title: {title}

Story:
{text}"""


def generate_script(story: dict, api_key: str) -> dict:
    log("Generating script via OpenRouter (gpt-4o-mini)…", "step")
    prompt_text = SCRIPT_PROMPT.replace("{title}", story["title"]).replace("{text}", story["selftext"])
    payload = {
        "model": OR_MODEL,
        "messages": [
            {"role": "system", "content": "You are a YouTube scriptwriter. Always return valid JSON."},
            {"role": "user", "content": prompt_text},
        ],
        "temperature": 0.8,
        "max_tokens": 8192,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/story-factory",
        "X-Title": "Story Factory",
    }
    resp = http_json(OR_URL, data=payload, headers=headers, timeout=120)
    raw = resp["choices"][0]["message"]["content"]

    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    parsed = json.loads(cleaned) if cleaned.startswith("{") else json.loads(re.search(r"\{[\s\S]*\}", cleaned).group())
    n = len(parsed.get("scenes", []))
    log(f"Script generated: {parsed.get('title', '?')} ({n} scenes)", "ok")
    return parsed


# ── Step 4: Generate scene images via Pollinations.ai ─────────────

PICSUM_URL = "https://picsum.photos/1920/1080?random={seed}"


def generate_scene_images(scenes: list[dict]) -> list[str]:
    log(f"Generating {len(scenes)} scene images…", "step")
    paths = []

    for i, scene in enumerate(scenes):
        sid = scene.get("id", i + 1)
        seed = int(time.time()) + i
        fname = f"scene_{sid:02d}.jpg"
        fpath = os.path.join(ASSETS_DIR, fname)

        # Try Pollinations.ai first
        prompt = scene.get("image_prompt", "")
        poll_url = "https://image.pollinations.ai/prompt/" + urllib.request.quote(prompt[:500]) + "?width=1920&height=1080&nofeed=true"
        log(f"  Scene {sid}: Pollinations.ai…", "info")
        try:
            img_data = http_binary(poll_url, timeout=60)
            with open(fpath, "wb") as f:
                f.write(img_data)
            paths.append(fpath)
            log(f"    Saved {fname} ({len(img_data) / 1024:.0f} KB)", "ok")
            time.sleep(1)
            continue
        except Exception:
            log(f"    Pollinations blocked, using picsum.photos…", "warn")

        # Fallback: picsum.photos
        picsum_url = PICSUM_URL.format(seed=seed)
        try:
            img_data = http_binary(picsum_url, timeout=30)
            with open(fpath, "wb") as f:
                f.write(img_data)
            paths.append(fpath)
            log(f"    Saved {fname} from picsum ({len(img_data) / 1024:.0f} KB)", "ok")
        except Exception as e:
            log(f"    Scene {sid} failed completely: {e}", "err")

    if not paths:
        raise RuntimeError("No images were generated")
    return paths


# ── Step 5: Generate narration via edge-tts ────────────────────────

async def generate_narration_edge(script_text: str) -> str:
    import edge_tts
    out_path = os.path.join(ASSETS_DIR, "narration.mp3")
    communicate = edge_tts.Communicate(script_text, "en-US-JennyNeural")
    await communicate.save(out_path)
    size = os.path.getsize(out_path)
    log(f"Narration saved ({size / 1024:.0f} KB)", "ok")
    return out_path


def generate_narration(script_text: str) -> str:
    log("Generating narration via edge-tts…", "step")
    return asyncio.run(generate_narration_edge(script_text))


# ── Step 6: Assemble video via FFmpeg ──────────────────────────────

def assemble_video(title: str) -> str:
    log("Assembling video via FFmpeg…", "step")
    safe = re.sub(r"[^a-zA-Z0-9]", "_", title)[:50]
    output_file = os.path.join(OUTPUT_DIR, f"{safe}.mp4")
    ps1 = os.path.join(BASE_DIR, "helpers", "assemble_video.ps1")
    cmd = [
        "powershell.exe",
        "-ExecutionPolicy", "Bypass",
        "-File", ps1,
        "-AssetsDir", ASSETS_DIR,
        "-OutputFile", output_file,
        "-Title", title,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    for line in result.stdout.splitlines():
        log(f"  {line}", "info")
    if result.returncode != 0:
        for line in result.stderr.splitlines():
            log(f"  ERR: {line}", "err")
        raise RuntimeError(f"Video assembly failed (exit code {result.returncode})")
    if not os.path.isfile(output_file):
        raise RuntimeError("Video file not found after assembly")
    log(f"Video created: {output_file}", "ok")
    return output_file


# ── Step 7: Log to production log ───────────────────────────────────

def save_log(entry: dict) -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    log_data = []
    if os.path.isfile(LOG_FILE):
        try:
            with open(LOG_FILE) as f:
                log_data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            log_data = []
    log_data.append(entry)
    with open(LOG_FILE, "w") as f:
        json.dump(log_data, f, indent=2)
    log("Production log updated", "ok")


# ── Main Pipeline ───────────────────────────────────────────────────

def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print()
    log("═══ Story Factory Pipeline ═══", "step")
    log(f"Pipeline: OpenRouter → Pollinations.ai → edge-tts → FFmpeg", "info")
    log(f"Assets: {ASSETS_DIR}", "info")
    log(f"Output: {OUTPUT_DIR}", "info")
    print()

    env = load_env()
    api_key = env.get("OPENROUTER_API_KEY") or env.get("GROQ_API_KEY", "")
    if not api_key or api_key.startswith("your"):
        log("Set OPENROUTER_API_KEY in .env first", "err")
        log("Get one free at https://openrouter.ai/keys", "info")
        sys.exit(1)

    t0 = time.time()
    try:
        posts = fetch_reddit_stories()
        story = pick_story(posts)
        script = generate_script(story, api_key)
        scene_paths = generate_scene_images(script.get("scenes", []))
        audio_path = generate_narration(script.get("script", ""))
        video_path = assemble_video(script.get("title", "Untitled"))

        entry = {
            "title": script.get("title", ""),
            "story_url": story.get("url", ""),
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "scenes": len(script.get("scenes", [])),
            "scene_images": [os.path.basename(p) for p in scene_paths],
            "audio_file": os.path.basename(audio_path),
            "video_file": os.path.basename(video_path),
            "elapsed_seconds": round(time.time() - t0),
            "stack": "OpenRouter + Pollinations.ai + edge-tts",
        }
        save_log(entry)

        elapsed = time.time() - t0
        print()
        log(f"Pipeline complete in {elapsed / 60:.1f} min", "ok")
        log(f"Video: {video_path}", "ok")
        print()

    except Exception as e:
        elapsed = time.time() - t0
        log(f"Pipeline FAILED after {elapsed / 60:.1f} min: {e}", "err")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
