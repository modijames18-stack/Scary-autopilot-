"""
Future-risk documentary autopilot.
Every run: research current future-risk topics -> write an evidence-aware scenario -> AI voice -> build video
-> post to YouTube + Facebook Page -> Telegram alerts (+ daily performance report).

Runs on GitHub Actions every 3 hours. Mix of short and long videos.
"""
import asyncio
import datetime as dt
import json
import os
import random
import re
import subprocess
import time
import traceback
from pathlib import Path

import requests
import anthropic

ROOT = Path(__file__).parent
HISTORY_FILE = ROOT / "history.json"
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)


def env(name, default=""):
    v = os.environ.get(name, "").strip()
    return v or default


MODEL = env("CLAUDE_MODEL", "claude-sonnet-5-5")
LONG_HOURS = [int(h) for h in env("LONG_HOURS", "6,18").split(",") if h.strip()]
YT_PRIVACY = env("YOUTUBE_PRIVACY", "private")  # switch to "public" once Google approves your app
YT_DAILY_CAP = int(env("YOUTUBE_DAILY_UPLOADS", "6"))  # default API quota allows ~6 uploads/day
REPORT_HOUR = int(env("REPORT_HOUR_UTC", "21"))
VOICE = env("TTS_VOICE", "en-US-ChristopherNeural")
NOW = dt.datetime.utcnow()
TODAY = NOW.strftime("%Y-%m-%d")


# ---------------------------------------------------------------- helpers
def notify(text):
    print(text)
    token, chat = env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text[:4000]},
            timeout=30,
        )
    except Exception as e:
        print("Telegram failed:", e)


def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text())
    return {"posts": [], "patterns": {}}


def save_history(h):
    h["posts"] = h["posts"][-500:]
    HISTORY_FILE.write_text(json.dumps(h, indent=2))


def run(cmd):
    r = subprocess.run(cmd, cwd=WORK, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd[:4])}...\n{r.stderr[-1500:]}")
    return r.stdout


def media_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def ai_provider():
    forced = env("AI_PROVIDER").lower()
    if forced in ("gemini", "anthropic"):
        return forced
    return "anthropic" if env("ANTHROPIC_API_KEY") else "gemini"


def ask_ai(system, prompt, max_tokens=4000, json_mode=False):
    """Free Gemini by default; switches to Claude when an Anthropic key is set."""
    if ai_provider() == "anthropic":
        client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")

    model = env("GEMINI_MODEL", "gemini-3.8-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    gen = {"maxOutputTokens": max(max_tokens, 2000) + 4000, "temperature": 1.0}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": dict(gen, thinkingConfig={"thinkingLevel": "low"}),
    }
    headers = {"x-goog-api-key": env("GEMINI_API_KEY"), "Content-Type": "application/json"}
    last = ""
    for attempt in range(6):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=120)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            last = f"network/timeout: {str(e)[:200]}"
            print("Gemini attempt", attempt + 1, "failed:", last)
            time.sleep(10)
            continue
        if r.status_code == 400 and "thinking" in r.text.lower():
            body["generationConfig"] = gen  # model does not support thinkingConfig
            continue
        if r.status_code in (429, 500, 503):
            last = r.text[:300]
            time.sleep(15 * (attempt + 1))
            continue
        if not r.ok:
            raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:400]}")
        parts = r.json()["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if text.strip():
            return text
        last = "empty answer"
    raise RuntimeError(f"Gemini kept failing: {last}")


def yt_credentials():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    creds = Credentials(
        None,
        refresh_token=env("YT_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=env("YT_CLIENT_ID"),
        client_secret=env("YT_CLIENT_SECRET"),
    )
    creds.refresh(Request())
    return creds


# ---------------------------------------------------------------- 1. research
def research(fmt, hist):
    """Research current public-interest future risks, cached once per day and format."""
    cached = hist["patterns"].get(fmt)
    if cached and cached.get("date") == TODAY:
        return cached["notes"]

    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=yt_credentials(), cache_discovery=False)
    since = (NOW - dt.timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    res = yt.search().list(
        q="AI jobs climate change water scarcity internet outage future technology risks",
        part="id", type="video", order="viewCount",
        videoDuration="short" if fmt == "short" else "medium",
        publishedAfter=since, maxResults=15, relevanceLanguage="en",
    ).execute()
    ids = [i["id"]["videoId"] for i in res.get("items", [])]
    if not ids:
        return "Research unavailable; rely on well-established evidence and clearly label uncertainty."
    vids = yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids)).execute()["items"]
    rows = [
        f"- \"{v['snippet']['title']}\" | {v['statistics'].get('viewCount', '?')} views"
        for v in vids
    ]
    notes = ask_ai(
        "You are a research assistant for a science and future-risk documentary channel.",
        "Review these popular videos only for audience-interest patterns, not as evidence. "
        "Suggest useful questions to investigate about AI and jobs, energy, water, climate, "
        "internet infrastructure, governance and other future risks. Do not repeat claims "
        "unless they can be verified with reliable evidence.\n" + "\n".join(rows),
        max_tokens=700,
    )
    hist["patterns"][fmt] = {"date": TODAY, "notes": notes}
    return notes


# ---------------------------------------------------------------- 2. script
def write_script(fmt, patterns, hist):
    recent = [p["title"] for p in hist["posts"][-40:]]
    if fmt == "short":
        spec = ("A SHORT vertical explainer, 120-150 spoken words, about 50 seconds. "
                "Open with a gripping question or plausible scenario. Explain one real risk "
                "and end with one practical solution plus a question for viewers.")
    else:
        spec = ("A LONG documentary, 900-1200 spoken words, about 6-8 minutes. "
                "Use a strong hook, clear sections, real-world evidence, competing viewpoints, "
                "uncertainties, impacts on ordinary people, practical solutions, and a thoughtful ending.")
    prompt = f"""Create an ORIGINAL, realistic, thought-provoking future-risk documentary for a faceless channel.
{spec}

Choose one topic per video, rotating among: AI replacing or changing jobs; concentration of power
and the hypothetical idea of one-world government; a worldwide internet or power outage; water
scarcity, drying rivers and drought; rivers turning red due to algae, pollution or other natural
causes; climate change and extreme weather; threats to food, health, energy and ecosystems; and
future technologies humanity may struggle to govern.

Research notes and audience-interest patterns (not proof):
{patterns}

Titles already used (avoid repeating them):
{recent}

Editorial rules:
- Separate established facts, credible forecasts, and hypothetical thought experiments.
- Never present an imagined catastrophe as a prediction or say it is happening without evidence.
- Explain causes, likelihood or uncertainty, who could be affected, and what people or communities can do.
- For claims about current events, science, statistics or forecasts, use cautious wording and name
  the type of reliable source viewers should consult; never invent studies, experts, statistics or quotes.
- For "one-world government", discuss governance, sovereignty, accountability and hypothetical risks
  without claiming a secret plan exists.
- For red rivers, explain real causes such as mineral runoff, algae or pollution; do not claim water
  has literally become blood.
- Use calm, serious, cinematic narration, plain spoken English, no gore, no fabricated eyewitnesses,
  and no fearmongering. Invite debate and constructive solutions.
- Visual search phrases must match the subject (data centres, workers, drought, rivers, power grids,
  satellites, farms, laboratories), not generic haunted-house footage.

Reply with ONLY a JSON object with these keys:
"title": under 85 characters, curiosity-driven, no hashtags,
"description": 2-3 accurate sentences that identify whether the scenario is hypothetical,
"tags": list of up to 10 short tags,
"narration": the full spoken text as one string,
"visual_keywords": list of 8 relevant stock-footage search phrases."""
    raw = ask_ai(
        "You are an investigative science communicator and future-risk documentary writer. "
        "Be compelling, evidence-aware, balanced, and solution-focused.",
        prompt, max_tokens=1200 if fmt == "short" else 5000, json_mode=True,
    )
    meta = parse_meta(raw)

    if fmt == "short":
        try:
            better = ask_ai(
                "You are a careful editor of short science and future-risk explainers.",
                "Improve this short documentary script. Strengthen the opening hook and end with "
                "a useful solution and question. Keep it factual, balanced, 120-150 words, plain "
                "spoken English. Clearly label hypothetical events. Reply with ONLY the same JSON "
                "object (same keys).\n\n" + json.dumps(meta),
                max_tokens=1200, json_mode=True,
            )
            meta = parse_meta(better)
        except Exception as e:
            print("Polish pass skipped:", e)
    return meta


def parse_meta(raw):
    start, end = raw.find("{"), raw.rfind("}")
    meta = json.loads(raw[start:end + 1], strict=False)
    for k in ("title", "description", "narration", "visual_keywords"):
        if k not in meta:
            raise ValueError(f"Script missing '{k}'")
    meta.setdefault("tags", [])
    return meta


# ---------------------------------------------------------------- 3. voice + captions
async def _tts(text, mp3_path):
    import edge_tts
    try:
        com = edge_tts.Communicate(text, VOICE, rate="-5%", boundary="WordBoundary")
    except TypeError:
        com = edge_tts.Communicate(text, VOICE, rate="-5%")
    words = []
    with open(mp3_path, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append((ch["offset"] / 1e7, ch["text"]))
    return words


def srt_time(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def make_voice_and_captions(fmt, narration):
    mp3 = WORK / "voice.mp3"
    words = asyncio.run(_tts(narration, mp3))
    duration = media_duration(mp3)
    if not words:  # fallback: spread words evenly
        toks = narration.split()
        step = duration / max(len(toks), 1)
        words = [(i * step, w) for i, w in enumerate(toks)]
    n = 4 if fmt == "short" else 7
    lines = []
    for i in range(0, len(words), n):
        grp = words[i:i + n]
        start = grp[0][0]
        end = words[i + n][0] if i + n < len(words) else duration
        if end <= start:
            end = start + 0.5
        lines.append(f"{len(lines) + 1}\n{srt_time(start)} --> {srt_time(end)}\n{' '.join(w for _, w in grp)}\n")
    (WORK / "captions.srt").write_text("\n".join(lines), encoding="utf-8")
    return duration


# ---------------------------------------------------------------- 4. video
def find_candidates(keywords, fmt, W):
    """Returns a list of (id, download_url, duration). Uses Pixabay (free key) or Pexels."""
    per_kw = []
    pix, pex = env("PIXABAY_API_KEY"), env("PEXELS_API_KEY")
    for kw in keywords[:8]:
        found = []
        try:
            if pix:
                r = requests.get("https://pixabay.com/api/videos/",
                                 params={"key": pix, "q": kw[:90], "per_page": 12, "safesearch": "true"},
                                 timeout=30)
                for h in r.json().get("hits", []):
                    vs = h.get("videos", {})
                    pick = vs.get("large") if vs.get("large", {}).get("url") else vs.get("medium")
                    if pick and pick.get("url"):
                        found.append((f"px{h['id']}", pick["url"], float(h.get("duration", 7))))
            elif pex:
                orient = "portrait" if fmt == "short" else "landscape"
                r = requests.get("https://api.pexels.com/videos/search",
                                 headers={"Authorization": pex},
                                 params={"query": kw, "orientation": orient, "per_page": 8}, timeout=30)
                for v in r.json().get("videos", []):
                    files = [f for f in v.get("video_files", [])
                             if f.get("file_type") == "video/mp4" and f.get("width")]
                    if not files:
                        continue
                    ok = [f for f in files if f["width"] >= W]
                    f = min(ok, key=lambda x: x["width"]) if ok else max(files, key=lambda x: x["width"])
                    found.append((f"pe{v['id']}", f["link"], float(v.get("duration", 7))))
        except Exception as e:
            print("Footage search failed:", kw, e)
        random.shuffle(found)
        per_kw.append(found[:4])
    return [lst[i] for i in range(4) for lst in per_kw if i < len(lst)]


def fetch_clips(keywords, fmt, need, W, H):
    max_clips = 12 if fmt == "short" else 36
    order = find_candidates(keywords, fmt, W)
    clips, seen, total = [], set(), 0.0
    for vid_id, link, vdur in order:
        if vid_id in seen or len(clips) >= max_clips or total >= need + 2:
            continue
        seen.add(vid_id)
        raw = WORK / f"raw_{vid_id}.mp4"
        seg = WORK / f"seg_{len(clips):02}.mp4"
        try:
            with requests.get(link, stream=True, timeout=90) as resp:
                resp.raise_for_status()
                with open(raw, "wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            d = min(vdur, 7.0)
            run(["ffmpeg", "-y", "-i", raw.name, "-t", str(d), "-an",
                 "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                        f"fps=30,eq=brightness=-0.06:saturation=0.75,setsar=1",
                 "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p", seg.name])
            clips.append((seg.name, d))
            total += d
        except Exception as e:
            print("Clip failed:", e)
        finally:
            raw.unlink(missing_ok=True)
    return clips


def build_video(fmt, meta, duration):
    W, H = (720, 1280) if fmt == "short" else (1280, 720)
    clips = fetch_clips(meta["visual_keywords"], fmt, duration, W, H)
    if clips:
        entries, total, i = [], 0.0, 0
        while total < duration + 1:
            name, d = clips[i % len(clips)]
            entries.append(f"file '{name}'")
            total += d
            i += 1
        (WORK / "list.txt").write_text("\n".join(entries))
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "visual.mp4"])
    else:  # fallback: plain dark background
        run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0a0a12:s={W}x{H}:d={duration + 1}:r=30",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "visual.mp4"])
    style = ("FontName=DejaVu Sans,Bold=1,FontSize=11,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BorderStyle=1,Outline=2,Alignment=2,MarginV=90") if fmt == "short" else \
            ("FontName=DejaVu Sans,Bold=1,FontSize=15,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BorderStyle=1,Outline=2,Alignment=2,MarginV=18")
    out = f"final_{fmt}.mp4"
    run(["ffmpeg", "-y", "-i", "visual.mp4", "-i", "voice.mp3",
         "-vf", f"subtitles=captions.srt:force_style='{style}'",
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
         "-c:a", "aac", "-b:a", "160k", "-t", f"{duration + 0.5:.2f}", out])
    return WORK / out


# ---------------------------------------------------------------- 5. publish
def hashtags(meta, fmt):
    tags = ["#future", "#technology", "#science", "#solutions"] + (["#shorts"] if fmt == "short" else [])
    return " ".join(tags)


def post_youtube(video, meta, fmt):
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    yt = build("youtube", "v3", credentials=yt_credentials(), cache_discovery=False)
    title = meta["title"][:88] + (" #Shorts" if fmt == "short" else "")
    body = {
        "snippet": {
            "title": title,
            "description": f"{meta['description']}\n\n{hashtags(meta, fmt)}\n\nAI-narrated future-risk explainer.",
            "tags": [str(t)[:30] for t in meta["tags"]][:10],
            "categoryId": "24",
        },
        "status": {
            "privacyStatus": YT_PRIVACY,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # honest AI disclosure
        },
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


def _fb_check(r):
    if not r.ok:
        raise RuntimeError(f"Facebook error {r.status_code}: {r.text[:500]}")
    return r.json()


def post_facebook(video, meta, fmt):
    page, token = env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")
    g = "https://graph.facebook.com/v21.0"
    desc = f"{meta['title']}\n\n{meta['description']}\n\n{hashtags(meta, fmt)}"
    if fmt == "short":  # Reel
        j = _fb_check(requests.post(f"{g}/{page}/video_reels",
                                    data={"upload_phase": "start", "access_token": token}, timeout=60))
        vid, up = j["video_id"], j["upload_url"]
        size = os.path.getsize(video)
        with open(video, "rb") as f:
            _fb_check(requests.post(up, headers={"Authorization": f"OAuth {token}",
                                                 "offset": "0", "file_size": str(size)},
                                    data=f, timeout=900))
        _fb_check(requests.post(f"{g}/{page}/video_reels",
                                data={"access_token": token, "video_id": vid, "upload_phase": "finish",
                                      "video_state": "PUBLISHED", "description": desc}, timeout=120))
        return vid
    with open(video, "rb") as f:  # normal video
        j = _fb_check(requests.post(f"{g}/{page}/videos",
                                    data={"access_token": token, "title": meta["title"], "description": desc},
                                    files={"source": f}, timeout=3000))
    return j.get("id")


# TikTok: add after TikTok approves your app (see SETUP.md). Until then it is skipped.


# ---------------------------------------------------------------- 6. report
def daily_report(hist):
    posts_today = [p for p in hist["posts"] if p["time"][:10] == TODAY]
    s = sum(1 for p in posts_today if p["format"] == "short")
    lines = [f"📊 Daily report {TODAY}",
             f"Posted today: {len(posts_today)} videos ({s} short, {len(posts_today) - s} long)"]

    if env("YT_REFRESH_TOKEN"):
        try:
            from googleapiclient.discovery import build
            creds = yt_credentials()
            yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
            st = yt.channels().list(part="statistics", mine=True).execute()["items"][0]["statistics"]
            lines.append(f"\n▶️ YouTube: {st.get('subscriberCount', 'hidden')} subs, "
                         f"{st.get('viewCount', 0)} total views, {st.get('videoCount', 0)} videos")
            ids = [p["youtube_id"] for p in hist["posts"] if p.get("youtube_id")][-50:]
            if ids:
                items = yt.videos().list(part="snippet,statistics", id=",".join(ids)).execute()["items"]
                items.sort(key=lambda v: int(v["statistics"].get("viewCount", 0)), reverse=True)
                top = items[0]
                lines.append(f"Top video: {top['snippet']['title'][:55]} ({top['statistics'].get('viewCount', 0)} views)")
            ya = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
            start = (NOW - dt.timedelta(days=7)).strftime("%Y-%m-%d")
            try:
                r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=TODAY,
                                       metrics="views,subscribersGained,estimatedRevenue").execute()
                row = (r.get("rows") or [[0, 0, 0]])[0]
                lines.append(f"Last 7 days: {row[0]} views, +{row[1]} subs, ${row[2]:.2f} est. revenue")
            except Exception:
                lines.append("Revenue: not available yet (channel not monetized, or permission missing)")
        except Exception as e:
            lines.append(f"YouTube report failed: {str(e)[:150]}")

    if env("FB_PAGE_TOKEN"):
        try:
            g = "https://graph.facebook.com/v21.0"
            page, token = env("FB_PAGE_ID"), env("FB_PAGE_TOKEN")
            info = _fb_check(requests.get(f"{g}/{page}", params={
                "fields": "fan_count,followers_count", "access_token": token}, timeout=30))
            lines.append(f"\n📘 Facebook: {info.get('followers_count', info.get('fan_count', '?'))} followers")
            try:
                vids = _fb_check(requests.get(f"{g}/{page}/videos", params={
                    "fields": "views", "limit": 25, "access_token": token}, timeout=30)).get("data", [])
                lines.append(f"Views on last {len(vids)} videos: {sum(v.get('views', 0) for v in vids)}")
            except Exception:
                lines.append("Video views: not available from Facebook right now")
            lines.append("Facebook earnings are not exposed to apps; check Meta Business Suite.")
        except Exception as e:
            lines.append(f"Facebook report failed: {str(e)[:150]}")

    lines.append("\n🎵 TikTok: not connected yet")
    notify("\n".join(lines))


# ---------------------------------------------------------------- main
def pick_format():
    forced = env("FORCE_FORMAT").lower()
    if forced in ("short", "long"):
        return forced
    return "long" if NOW.hour in LONG_HOURS else "short"


def main():
    hist = load_history()
    if env("REPORT_ONLY") == "true":
        daily_report(hist)
        return

    fmt = pick_format()
    try:
        try:
            patterns = research(fmt, hist)
        except Exception as e:
            print("Research failed:", e)
            patterns = "(research unavailable; use general viral horror storytelling best practice)"
        meta = write_script(fmt, patterns, hist)
        duration = make_voice_and_captions(fmt, meta["narration"])
        video = build_video(fmt, meta, duration)
    except Exception:
        notify(f"❌ Video creation failed ({fmt}):\n{traceback.format_exc()[-1500:]}")
        save_history(hist)
        raise SystemExit(1)

    record = {"time": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "format": fmt, "title": meta["title"]}
    msgs = []

    yt_today = sum(1 for p in hist["posts"] if p.get("youtube_id") and p["time"][:10] == TODAY)
    if env("YT_REFRESH_TOKEN") and yt_today < YT_DAILY_CAP:
        try:
            record["youtube_id"] = post_youtube(video, meta, fmt)
            msgs.append(f"▶️ YouTube ({YT_PRIVACY}): https://youtu.be/{record['youtube_id']}")
        except Exception as e:
            notify(f"❌ YouTube upload failed: {str(e)[:700]}")
    elif env("YT_REFRESH_TOKEN"):
        msgs.append("▶️ YouTube skipped: daily upload cap reached")

    if env("FB_PAGE_TOKEN") and env("FB_PAGE_ID"):
        try:
            record["facebook_id"] = post_facebook(video, meta, fmt)
            msgs.append(f"📘 Facebook: posted ({record['facebook_id']})")
        except Exception as e:
            notify(f"❌ Facebook post failed: {str(e)[:700]}")

    hist["posts"].append(record)
    save_history(hist)
    notify(f"✅ New {fmt} video: {meta['title']}\n" + "\n".join(msgs))

    if NOW.hour == REPORT_HOUR:
        daily_report(hist)


if __name__ == "__main__":
    main()
