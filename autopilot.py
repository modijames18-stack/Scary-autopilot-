"""
Future-risk documentary autopilot.
Every run: research current future-risk topics -> write an evidence-aware scenario -> AI voice -> build video
-> publish to YouTube, Facebook, Instagram and TikTok inbox -> Telegram alerts (+ daily performance report).

Runs on GitHub Actions every 3 hours. Each scheduled run creates one vertical short for all enabled platforms.
"""
import asyncio
import datetime as dt
import json
import hashlib
import os
import random
import re
import subprocess
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse

import requests
import anthropic

from evidence_library import TOPICS, evidence_catalogue_text, sources_for_topic

ROOT = Path(__file__).parent
HISTORY_FILE = ROOT / "history.json"
WORK = ROOT / "work"
WORK.mkdir(exist_ok=True)


def env(name, default=""):
    v = os.environ.get(name, "").strip()
    return v or default


def github_run_context():
    """Attach non-secret GitHub Actions identifiers to the persisted run record."""
    return {
        "github_run_id": env("GITHUB_RUN_ID") or None,
        "github_run_attempt": env("GITHUB_RUN_ATTEMPT") or None,
        "github_event": env("GITHUB_EVENT_NAME") or "local",
    }


def delivery_completion_status(platforms):
    """Only mark the run fully delivered when all four configured handoffs are verified."""
    expected = {
        "youtube": "verified_upload",
        "facebook": "verified_publish",
        "instagram": "verified_publish",
        # TikTok's permitted video.upload integration is an inbox handoff, not a public post.
        "tiktok": "inbox_uploaded",
    }
    if all(platforms.get(name, {}).get("status") == status
           for name, status in expected.items()):
        return "completed"
    return "completed_with_delivery_issues"


def publishing_enabled(variable):
    """Publishing is opt-in; missing or non-true switches always disable uploads."""
    return env(variable).lower() == "true"


MODEL = env("CLAUDE_MODEL", "claude-sonnet-5-5")
LONG_HOURS = [int(h) for h in env("LONG_HOURS", "6,18").split(",") if h.strip()]
YT_PRIVACY = env("YOUTUBE_PRIVACY", "private")  # switch to "public" once Google approves your app
YT_DAILY_CAP = int(env("YOUTUBE_DAILY_UPLOADS", "8"))  # one upload per 3-hour run
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
        history = json.loads(HISTORY_FILE.read_text())
    else:
        history = {}
    history.setdefault("posts", [])
    history.setdefault("patterns", {})
    history.setdefault("runs", [])
    return history


def save_history(h):
    h.setdefault("posts", [])
    h.setdefault("patterns", {})
    h.setdefault("runs", [])
    h["posts"] = h["posts"][-500:]
    h["runs"] = h["runs"][-500:]
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


def safe_ai_error_summary(exc):
    """Return actionable provider diagnostics without copying raw API responses or secrets."""
    message = str(exc).lower()
    provider = ai_provider()
    if provider == "gemini":
        if "quota" in message and ("exceed" in message or "limit" in message or "429" in message):
            return (
                "Gemini API quota or billing limit reached. Check Google AI Studio usage and "
                "billing, or configure ANTHROPIC_API_KEY and set AI_PROVIDER=anthropic."
            )
        if "429" in message or "resource_exhausted" in message or "rate limit" in message:
            return (
                "Gemini API rate limit reached after bounded retries. Check model limits or "
                "configure ANTHROPIC_API_KEY with AI_PROVIDER=anthropic."
            )
        if "timeout" in message or "timed out" in message:
            return (
                "Gemini API timed out after bounded retries. Check provider availability or "
                "configure ANTHROPIC_API_KEY with AI_PROVIDER=anthropic."
            )
        if any(token in message for token in ("401", "403", "unauthorized", "permission denied")):
            return "Gemini API authentication or permission failed. Verify GEMINI_API_KEY and Google AI Studio project access."
        return "Gemini API request failed after bounded retries; inspect redacted workflow diagnostics."

    if "quota" in message or "billing" in message or "credit" in message:
        return "Anthropic API quota or billing limit reached. Check the Anthropic account's usage and billing."
    if "timeout" in message or "timed out" in message:
        return "Anthropic API timed out. Check provider availability and retry the next scheduled slot."
    if any(token in message for token in ("401", "403", "unauthorized", "permission denied")):
        return "Anthropic API authentication or permission failed. Verify ANTHROPIC_API_KEY and model access."
    return "Anthropic API request failed; inspect redacted workflow diagnostics."


def gemini_model_sequence():
    """Return the configured primary Gemini model followed by safe, low-cost fallbacks."""
    primary = env("GEMINI_MODEL", "gemini-3.8-flash")
    fallback = env("GEMINI_FALLBACK_MODELS", "gemini-3.6-flash")
    models = []
    for candidate in [primary, *fallback.split(",")]:
        name = candidate.strip()
        if name.startswith("models/"):
            name = name[len("models/"):]
        if name and name not in models:
            models.append(name)
    return models


def ask_ai(system, prompt, max_tokens=4000, json_mode=False):
    """Use the configured writer; bound Gemini retries and fail over without weakening checks."""
    if ai_provider() == "anthropic":
        client = anthropic.Anthropic(api_key=env("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=MODEL, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text")

    models = gemini_model_sequence()
    attempts_per_model = max(1, min(3, int(env("GEMINI_ATTEMPTS_PER_MODEL", "2"))))
    timeout_seconds = max(15, min(180, int(env("GEMINI_TIMEOUT_SECONDS", "75"))))
    # Short scripts and scene plans do not need the old 6,000-token minimum.
    # Smaller output ceilings reduce latency and free-tier quota use.
    gen = {"maxOutputTokens": max(int(max_tokens), 512), "temperature": 1.0}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    headers = {"x-goog-api-key": env("GEMINI_API_KEY"), "Content-Type": "application/json"}
    failures = []

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": dict(gen, thinkingConfig={"thinkingLevel": "low"}),
        }
        thinking_enabled = True
        for attempt in range(attempts_per_model):
            try:
                response = requests.post(
                    url, headers=headers, json=body, timeout=timeout_seconds
                )
            except requests.exceptions.RequestException as exc:
                reason = f"network error: {type(exc).__name__}: {str(exc)[:160]}"
                failures.append(f"{model}: {reason}")
                print(f"Gemini {model} attempt {attempt + 1}/{attempts_per_model} failed: {reason}")
                if attempt + 1 < attempts_per_model:
                    time.sleep(min(5 * (attempt + 1), 10))
                continue

            if response.status_code == 400 and thinking_enabled and "thinking" in response.text.lower():
                body["generationConfig"] = gen
                thinking_enabled = False
                print(f"Gemini {model} does not accept thinkingConfig; retrying without it.")
                continue

            if response.status_code in (408, 429, 500, 502, 503, 504):
                response_text = str(getattr(response, "text", "")).lower()
                hard_quota = response.status_code == 429 and any(
                    marker in response_text
                    for marker in (
                        "you exceeded your current quota",
                        "quota exceeded for metric",
                        "quotaexceeded",
                    )
                )
                if hard_quota:
                    failures.append(f"{model}: quota exhausted (HTTP 429)")
                    print(
                        f"Gemini {model} quota is exhausted; skipping redundant retries "
                        "and trying the next configured model."
                    )
                    break

                reason = f"HTTP {response.status_code}: {response.text[:160]}"
                failures.append(f"{model}: {reason}")
                print(f"Gemini {model} attempt {attempt + 1}/{attempts_per_model} failed: {reason}")
                if attempt + 1 < attempts_per_model:
                    time.sleep(min(5 * (attempt + 1), 10))
                continue

            if response.status_code == 404:
                reason = f"model unavailable (HTTP 404): {response.text[:120]}"
                failures.append(f"{model}: {reason}")
                print(f"Gemini {model} is unavailable; trying the next configured model.")
                break

            if not response.ok:
                raise RuntimeError(
                    f"Gemini error {response.status_code}: {response.text[:300]}"
                )

            try:
                candidates = response.json().get("candidates", [])
                parts = candidates[0].get("content", {}).get("parts", [])
            except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
                failures.append(f"{model}: malformed response ({type(exc).__name__})")
                break

            generated = "".join(
                part.get("text", "") for part in parts if not part.get("thought")
            )
            if generated.strip():
                return generated
            failures.append(f"{model}: empty response")
            break

        print(f"Gemini model {model} exhausted; moving to the next fallback if available.")

    summary = "; ".join(failures[-4:]) or "no Gemini model is configured"
    raise RuntimeError(f"Gemini models unavailable after bounded retries: {summary}")


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
    if not env("YT_REFRESH_TOKEN") or not publishing_enabled("ENABLE_YOUTUBE_UPLOAD"):
        return ("Audience-interest research skipped because YouTube publishing is disabled or OAuth "
                "is not configured; use the curated evidence catalogue and do not treat popularity as proof.")
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


TOPIC_ROTATION = [
    "Water scarcity and drying rivers",
    "AI and jobs",
    "Climate change, extreme weather and food security",
    "Power-grid resilience and worldwide blackout scenarios",
    "Ocean warming, sea-level rise and glacier loss",
    "Global AI governance and concentration of power",
    "Air pollution and health",
    "Internet infrastructure and global connectivity",
    "Red or discolored rivers and harmful algal blooms",

]

# Topic-specific editorial profiles are deterministic guardrails, not a substitute
# for human review of nuanced factual claims.
TOPIC_FACT_ATTRIBUTIONS = {
    "Water scarcity and drying rivers": (
        r"\bUN[- ]Water\b", r"\bUNU[- ]INWEH\b", r"\bUnited Nations University\b",
    ),
    "AI and jobs": (r"\bILO\b", r"\bInternational Labour Organization\b"),
    "Global AI governance and concentration of power": (
        r"\bUnited Nations\b", r"\bUN Global Risk Report\b", r"\bUN (?:scientific )?panel\b",
    ),
    "Power-grid resilience and worldwide blackout scenarios": (
        r"\bIEA\b", r"\bInternational Energy Agency\b",
    ),
    "Internet infrastructure and global connectivity": (
        r"\bITU\b", r"\bInternational Telecommunication Union\b",
    ),
    "Climate change, extreme weather and food security": (
        r"\bIPCC\b", r"\bIntergovernmental Panel on Climate Change\b",
    ),
    "Ocean warming, sea-level rise and glacier loss": (
        r"\bWMO\b", r"\bWorld Meteorological Organization\b",
    ),
    "Air pollution and health": (r"\bWHO\b", r"\bWorld Health Organization\b"),
    "Red or discolored rivers and harmful algal blooms": (
        r"\bNOAA\b", r"\bEPA\b", r"\bEnvironmental Protection Agency\b",
    ),
}

TOPIC_FACT_TERMS = {
    "Water scarcity and drying rivers": r"\b(?:water|river|scarcity|drought|aquifer|groundwater|basin)\b",
    "AI and jobs": r"\b(?:AI|artificial intelligence|generative AI|jobs?|employment|workplace)\b",
    "Global AI governance and concentration of power": r"\b(?:AI|artificial intelligence|governance|concentration of power|global risk)\b",
    "Power-grid resilience and worldwide blackout scenarios": r"\b(?:power|electricity|grid|energy|outage|resilience)\b",
    "Internet infrastructure and global connectivity": r"\b(?:internet|submarine cable|cable|connectivity|network)\b",
    "Climate change, extreme weather and food security": r"\b(?:climate|heat|drought|flood|extreme weather|food security)\b",
    "Ocean warming, sea-level rise and glacier loss": r"\b(?:ocean|sea level|glacier|marine|ocean heat|warming)\b",
    "Air pollution and health": r"\b(?:air pollution|pollution|particulate|smog|air quality)\b",
    "Red or discolored rivers and harmful algal blooms": r"\b(?:river|algal|bloom|cyanobacteria|water|discoloration)\b",
}

TOPIC_VISUAL_TERMS = {
    "Water scarcity and drying rivers": {
        "water", "river", "drought", "dry", "drying", "reservoir", "groundwater",
        "aquifer", "basin", "irrigation", "scarcity", "well", "wetland", "farmer",
        "farmers", "crop", "crops", "pipe", "rain",
    },
    "AI and jobs": {
        "ai", "artificial", "intelligence", "automation", "worker", "workers", "job",
        "jobs", "employment", "workplace", "robot", "robots", "office", "factory",
        "factories", "training", "skills",
    },
    "Global AI governance and concentration of power": {
        "ai", "artificial", "intelligence", "governance", "regulation", "policy",
        "power", "technology", "algorithm", "algorithms", "data", "computing",
    },
    "Power-grid resilience and worldwide blackout scenarios": {
        "power", "electricity", "grid", "blackout", "energy", "transmission",
        "substation", "transformer", "solar", "wind", "outage", "utility", "utilities",
    },
    "Internet infrastructure and global connectivity": {
        "internet", "submarine", "cable", "cables", "fibre", "fiber", "network",
        "data", "satellite", "connectivity", "telecom", "server", "repair", "ship",
    },
    "Climate change, extreme weather and food security": {
        "climate", "heat", "weather", "drought", "flood", "storm", "food", "crop",
        "farm", "farming", "precipitation", "extreme", "emissions", "wildfire",
    },
    "Ocean warming, sea-level rise and glacier loss": {
        "ocean", "sea", "glacier", "ice", "coast", "coastal", "warming", "coral",
        "marine", "water", "heat", "sea-level",
    },
    "Air pollution and health": {
        "air", "pollution", "particulate", "smog", "emissions", "health", "lungs",
        "vehicle", "factory", "monitor", "air-quality",
    },
    "Red or discolored rivers and harmful algal blooms": {
        "river", "algae", "algal", "bloom", "water", "discolored", "red",
        "cyanobacteria", "nutrient", "runoff", "lake", "sample", "testing",
    },
}

BANNED_VISUAL_PATTERN = re.compile(
    r"\b(?:haunted|ghost|phantom|monster|demon|horror|creepy|blood|"
    r"dark hallway|dark corridor|black forest|abandoned house|abandoned hallway|"
    r"mysterious door|no reflection|ghost train|phone ringing)\b",
    re.IGNORECASE,
)
GENERIC_VISUAL_TERMS = {
    "nature", "people", "city", "landscape", "footage", "video", "cinematic",
    "background", "scenery", "beautiful", "dark", "forest", "building",
    "technology", "documentary", "scene", "shot", "stock",
}


def choose_topic(hist):
    """Advance the curated rotation after every attempted episode, not only successful posts."""
    runs = hist.get("runs", [])
    posts = hist.get("posts", [])
    previous = next(
        (item.get("topic") for item in reversed(runs) if item.get("topic") in TOPICS),
        None,
    )
    if previous is None:
        previous = next(
            (item.get("topic") for item in reversed(posts) if item.get("topic") in TOPICS),
            None,
        )
    try:
        start = TOPIC_ROTATION.index(previous)
    except ValueError:
        start = -1
    for offset in range(1, len(TOPIC_ROTATION) + 1):
        candidate = TOPIC_ROTATION[(start + offset) % len(TOPIC_ROTATION)]
        if candidate in TOPICS:
            return candidate
    raise RuntimeError("No curated documentary topics are available")


# ---------------------------------------------------------------- 2. script
def write_script(fmt, patterns, hist, topic=None, include_visual_plan=True):
    topic = topic or choose_topic(hist)
    if topic not in TOPICS:
        raise ValueError(f"Topic is not in the curated evidence catalogue: {topic}")
    recent = [p["title"] for p in hist["posts"][-40:]]
    recent_topics = [p.get("topic", "unknown") for p in hist["posts"][-8:]]
    evidence_catalogue = evidence_catalogue_text()
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

This episode's required topic is exactly: {topic}
Do not switch to a different topic. The topic was selected by a deliberate rotation from the
curated evidence catalogue, not randomly. Environmental investigations are intentionally frequent,
including water scarcity, climate extremes, ocean warming, glacier loss, air pollution, and river
ecosystem health. Other episodes cover AI, jobs, energy, and infrastructure risks.

Research notes and audience-interest patterns (not proof):
{patterns}

Curated authoritative evidence catalogue (use this as the factual starting point; do not invent claims or URLs):
{evidence_catalogue}

Use the exact required topic above and its matching evidence section from the catalogue. The hypothetical idea of a single world government must remain explicitly hypothetical; existing UN cooperation is not a world government.

Titles already used (avoid repeating them):
{recent}

Recent topics already covered (avoid unnecessary immediate repetition):
{recent_topics}

Investigative documentary rules (mandatory):
- Make this feel like a high-quality investigative documentary, NEVER a fictional horror story.
- Open with a striking question or documented real-world development, not an invented character,
  fake emergency broadcast, fictional town, or fabricated eyewitness.
- Build a clear investigation: what is happening now; what reliable evidence shows; what experts
  disagree about; what could plausibly happen next; who would be affected; and what solutions exist.
- The narration MUST use three clearly separated spoken labels: "FACT:", "FORECAST:", and "WHAT-IF:".
  FACT contains only documented evidence from the matching catalogue topic and explicitly names an\n  institution from that topic's catalogue. FORECAST describes a
  credible, qualified future risk and its uncertainty. WHAT-IF is explicitly hypothetical and must
  never be presented as an event that has happened or a prediction that is certain.
- Use specific, checkable evidence. Never invent statistics, studies, report titles, quotations,
  experts, dates, or source URLs. If a precise claim cannot be supported, omit it or qualify it.
- Ground factual statements in the supplied evidence catalogue. Do not invent statistics, study findings, source titles, or URLs. Keep forecasts and what-if scenarios clearly separate from documented facts.
- The application will attach the exact reachable sources from the selected catalogue topic. Do not substitute other sources.
- Explain uncertainty, limitations, and competing viewpoints fairly. Avoid claiming that a forecast
  is certain or that a worst-case scenario is inevitable.
- Use serious, confident, human narration; cinematic pacing, meaningful pauses, and suspense created
  by evidence and unanswered questions—not fake scares, gore, or exaggerated claims.
- End with practical responses and make the final spoken sentence a thoughtful viewer question ending in a question mark. Do not place a sign-off or any text after it.
- Visual search phrases must describe authentic documentary footage relevant to each section:
  real workplaces, workers, data centres, power grids, reservoirs, rivers, farms, laboratories,
  scientific fieldwork, public infrastructure, and affected communities. Never request haunted-house
  imagery or visuals that falsely imply a hypothetical event is real.
- Research notes above indicate audience interest only; they are NOT factual evidence.

Reply with ONLY a JSON object with these keys:
"topic": exact topic name selected from the evidence catalogue,
"title": under 85 characters, specific and curiosity-driven, no hashtags,
"description": 2-3 accurate sentences; disclose clearly if discussing a hypothetical scenario,
"tags": list of up to 10 short tags,
"narration": the full spoken text as one string,
"visual_keywords": list of 8-12 relevant documentary-footage search phrases,
"sources": list of 2-5 objects, each with "title", "url", and "supports" (the claim it supports)."""
    raw = ask_ai(
        "You are an investigative science communicator and future-risk documentary writer. "
        "Be compelling, evidence-aware, balanced, and solution-focused.",
        prompt, max_tokens=1200 if fmt == "short" else 5000, json_mode=True,
    )
    meta = ensure_viewer_question(parse_meta(raw), fmt)
    meta = validate_documentary_script(
        verify_source_links(meta), expected_topic=topic, fmt=fmt
    )

    if fmt == "short":
        try:
            better = ask_ai(
                "You are a careful editor of short science and future-risk explainers.",
                "Improve this short investigative documentary script. Keep it evidence-led, never "
                "turn it into fictional horror. Preserve real source entries and all supported facts; "
                "do not add unsupported claims or invent sources. Strengthen the hook, keep it balanced, "
                "120-150 words, and end with a practical response and question. Clearly label hypotheticals. "
                "Reply with ONLY the same JSON object (same keys).\n\n" + json.dumps(meta),
                max_tokens=1200, json_mode=True,
            )
            polished = ensure_viewer_question(parse_meta(better), fmt)
            meta = validate_documentary_script(
                verify_source_links(polished), expected_topic=topic, fmt=fmt
            )
        except Exception as e:
            print("Polish pass skipped:", e)
    if include_visual_plan:
        meta["visual_scenes"] = make_visual_plan(meta["narration"], topic=topic)
    return meta


def make_visual_plan(narration, topic=None):
    """Create ordered, narration-specific searches and reject unrelated or horror imagery."""
    sentences = re.split(r"(?<=[.!?])\s+", narration.strip())
    chunks = [" ".join(sentences[i:i + 3]).strip() for i in range(0, len(sentences), 3)]
    chunks = [chunk for chunk in chunks if chunk]
    if not chunks:
        raise ValueError("Narration is empty; cannot plan documentary scenes.")
    numbered = "\n".join(f"{i + 1}. {chunk}" for i, chunk in enumerate(chunks))
    raw = ask_ai(
        "You are a documentary footage researcher. Match visuals precisely to narration. "
        "Never imply that illustrative footage documents an event it does not show.",
        "For each numbered narration segment, return 2-4 concise, concrete search phrases "
        "for authentic documentary footage that directly depicts that segment. Use the "
        "episode's real subject, systems, workers, instruments or ecosystems. Do not use "
        "horror, haunted-house, fictional-character, fantasy or generic mood imagery. Keep "
        "the same order and number of scenes. If a claim is hypothetical, use clearly "
        "illustrative real-world subject footage, never fake news imagery. Return ONLY JSON: "
        '{"scenes":[{"index":1,"keywords":["...","..."]}]}\n\n' + numbered,
        max_tokens=1800, json_mode=True,
    )
    data = json.loads(raw[raw.find("{"):raw.rfind("}") + 1])
    scenes = data.get("scenes", [])
    if len(scenes) != len(chunks):
        raise ValueError("AI footage plan did not return one scene for every narration segment.")
    topic_terms = TOPIC_VISUAL_TERMS.get(topic, set())
    plan = []
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "are", "was",
        "were", "will", "could", "would", "should", "have", "has", "had", "its",
        "their", "they", "them", "then", "than", "when", "where", "what", "which",
        "who", "how", "why", "about", "after", "before", "while", "because", "there",
        "these", "those", "some", "more", "most", "many", "much", "very", "already",
        "also", "only", "not", "but", "yet", "can", "may", "might", "if", "as",
        "at", "by", "on", "in", "of", "to", "a", "an", "is", "it",
    }
    for expected, item in enumerate(scenes, 1):
        if item.get("index") != expected or not isinstance(item.get("keywords"), list):
            raise ValueError("AI footage plan has missing or out-of-order scene indexes.")
        keywords = [str(k).strip() for k in item["keywords"] if str(k).strip()][:4]
        if len(keywords) < 2:
            raise ValueError(f"Scene {expected} has too few specific footage searches.")
        scene_terms = set(re.findall(r"[a-z0-9]+", chunks[expected - 1].lower())) - stopwords
        keyword_terms = []
        for keyword in keywords:
            if BANNED_VISUAL_PATTERN.search(keyword):
                raise ValueError(
                    f"Scene {expected} requested fictional or horror footage: {keyword!r}."
                )
            tokens = set(re.findall(r"[a-z0-9]+", keyword.lower()))
            meaningful = tokens - GENERIC_VISUAL_TERMS
            if len(meaningful) < 1:
                raise ValueError(f"Scene {expected} contains a generic footage search: {keyword!r}.")
            if topic and not (tokens & scene_terms or tokens & topic_terms):
                raise ValueError(
                    f"Scene {expected} footage search does not match its narration or topic: {keyword!r}."
                )
            keyword_terms.append(tokens)
        if topic and not any(tokens & topic_terms for tokens in keyword_terms):
            raise ValueError(
                f"Scene {expected} has no footage search anchored to the documentary topic {topic!r}."
            )
        if topic and not any(tokens & scene_terms for tokens in keyword_terms):
            raise ValueError(
                f"Scene {expected} has no footage search tied to its specific narration segment."
            )
        plan.append({"text": chunks[expected - 1], "keywords": keywords})
    return plan


def parse_meta(raw):
    start, end = raw.find("{"), raw.rfind("}")
    meta = json.loads(raw[start:end + 1], strict=False)
    for k in ("topic", "title", "description", "narration", "visual_keywords"):
        if k not in meta:
            raise ValueError(f"Script missing '{k}'")
    meta.setdefault("tags", [])
    meta.setdefault("sources", [])
    if not isinstance(meta["sources"], list):
        raise ValueError("Script sources must be a list")
    if not isinstance(meta["visual_keywords"], list) or len(meta["visual_keywords"]) < 4:
        raise ValueError("Script must include at least four documentary footage search phrases")
    return meta


def ensure_viewer_question(meta, fmt):
    """Guarantee a spoken closing question without changing evidence or sources."""
    narration = str(meta.get("narration", "")).strip()
    # Treat a question followed by closing quotation marks as a valid ending.
    if re.search(r"\?\s*[\"'”’)]*\s*$", narration):
        return meta
    closing_question = "What should we do first?"
    repaired = (narration.rstrip() + " " + closing_question).strip()
    words = re.findall(r"\b[\w’'-]+\b", repaired)
    if fmt == "short" and len(words) > 160:
        raise ValueError(
            "Short documentary narration is too long to add its required closing question "
            f"without editing evidence; got {len(words)} words."
        )
    meta["narration"] = repaired
    return meta


def validate_documentary_script(meta, expected_topic, fmt):
    """Deterministic editorial gate for topic, evidence attribution and documentary framing."""
    if meta.get("topic") != expected_topic:
        raise ValueError(
            f"Script topic drift: expected {expected_topic!r}, got {meta.get('topic')!r}"
        )
    narration = str(meta.get("narration", "")).strip()
    words = re.findall(r"\b[\w’'-]+\b", narration)
    if fmt == "short" and not 110 <= len(words) <= 160:
        raise ValueError(
            f"Short documentary narration must contain 110-160 words; got {len(words)}."
        )

    # Reject recognisable fictional-horror framing before voice or video is rendered.
    fiction_patterns = (
        (r"\b(?:[Oo]ne|[Tt]hat)\s+(?:[Mm]orning|[Nn]ight|[Ee]vening)\s+when\s+[A-Z][a-z]{2,}\b", 0),
        (r"\b(?:a|the)\s+(?:man|woman|boy|girl|family|town|village)\s+(?:named|called)\b", re.IGNORECASE),
        (r"\b(?:ghost|haunted|phantom|monster|demon|no reflection|the phone rang|a phone rang|"
         r"the last train to|the house that|the road that)\b", re.IGNORECASE),
        (r"\b(?:he|she)\s+(?:heard|opened|switched on)\s+(?:a|the)\s+(?:door|phone|radio)\b",
         re.IGNORECASE),
    )
    if any(re.search(pattern, narration, flags) for pattern, flags in fiction_patterns):
        raise ValueError(
            "Fictional story framing detected; documentary narration must investigate real evidence, "
            "not invented characters, events or horror tropes."
        )

    label_patterns = {
        "FACT": r"\bFACT\s*:",
        "FORECAST": r"\bFORECAST\s*:",
        "WHAT-IF": r"\bWHAT[- ]IF\s*:",
    }
    matches = {label: re.search(pattern, narration, flags=re.IGNORECASE)
               for label, pattern in label_patterns.items()}
    missing = [label for label, match in matches.items() if not match]
    if missing:
        raise ValueError(
            "Documentary narration must clearly separate FACT, FORECAST, and WHAT-IF; "
            f"missing labels: {', '.join(missing)}."
        )
    positions = [matches[label].start() for label in ("FACT", "FORECAST", "WHAT-IF")]
    if positions != sorted(positions):
        raise ValueError("FACT, FORECAST and WHAT-IF sections must appear in that order.")
    if len(re.findall(r"\b[\w’'-]+\b", narration[:positions[0]])) > 24:
        raise ValueError("The opening must not contain a long unlabelled story before FACT.")

    fact = narration[matches["FACT"].end():matches["FORECAST"].start()].strip()
    forecast = narration[matches["FORECAST"].end():matches["WHAT-IF"].start()].strip()
    what_if = narration[matches["WHAT-IF"].end():].strip()

    institutions = TOPIC_FACT_ATTRIBUTIONS.get(expected_topic, ())
    if not institutions or not any(re.search(pattern, fact, re.IGNORECASE) for pattern in institutions):
        raise ValueError(
            "FACT section must explicitly attribute a documented claim to an institution "
            "from the matching evidence catalogue."
        )
    fact_terms = TOPIC_FACT_TERMS.get(expected_topic)
    if not fact_terms or not re.search(fact_terms, fact, re.IGNORECASE):
        raise ValueError("FACT section does not contain a clear factual claim about the selected topic.")
    if not re.search(
        r"\b(?:could|may|might|possible|possibly|potential|risk|projected|projection|"
        r"forecast|uncertain|uncertainty|depends|depending|under certain conditions)\b",
        forecast, re.IGNORECASE,
    ):
        raise ValueError("FORECAST section must qualify uncertainty rather than state certainty.")
    if not re.search(r"\b(?:if|imagine|hypothetical|scenario)\b", what_if, re.IGNORECASE):
        raise ValueError("WHAT-IF section must explicitly identify its scenario as hypothetical.")

    if not re.search(
        r"\b(?:conserve|repair|protect|restore|monitor|prepare|adapt|invest|reduce|improve|"
        r"strengthen|regulate|train|reskill|plan|share|upgrade|maintain|diversify|transition|"
        r"build|switch|fund|recycle|support)\b",
        " ".join(narration.split()[-70:]), re.IGNORECASE,
    ):
        raise ValueError("Documentary narration must include a practical response or solution.")
    if not narration.endswith("?"):
        raise ValueError("Documentary narration must end with a thoughtful viewer question.")
    if len(meta.get("sources", [])) < 2:
        raise ValueError("Documentary must cite at least two curated institutional sources.")
    if not str(meta.get("title", "")).strip() or len(str(meta["title"])) >= 85:
        raise ValueError("Documentary title must be 1-84 characters.")
    if not str(meta.get("description", "")).strip():
        raise ValueError("Documentary description is required.")
    return meta


def verify_source_links(meta):
    """Use curated, allowlisted institutional sources without failing on transient site blocks.

    A source is accepted only when it comes from the repository's evidence catalogue,
    uses HTTPS, and belongs to an approved institution. Network reachability is logged
    as diagnostic information only: public institutions sometimes rate-limit automated
    requests, and a temporary block must not erase otherwise valid evidence.
    """
    topic = str(meta.get("topic", "")).strip()
    candidates = sources_for_topic(topic)
    if len(candidates) < 2:
        raise ValueError(f"Unknown or unsupported documentary topic: {topic!r}")

    trusted_domains = (
        "ilo.org", "un.org", "unwater.org", "iea.org", "itu.int",
        "ipcc.ch", "noaa.gov", "epa.gov", "wmo.int", "who.int",
    )
    approved = []
    for source in candidates:
        url = str(source.get("url", "")).strip()
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        trusted = any(host == domain or host.endswith("." + domain) for domain in trusted_domains)
        if parsed.scheme != "https" or not trusted:
            print("Rejected non-approved evidence URL:", url)
            continue
        if not parsed.path and not parsed.query:
            print("Rejected incomplete evidence URL:", url)
            continue
        approved.append(source)

        # Reachability is useful telemetry, not a publication gate. Keep curated
        # citations when a government/university site rate-limits or blocks CI.
        try:
            response = requests.get(
                url, timeout=12,
                headers={"User-Agent": "ScaryAutopilotResearch/1.0"},
                allow_redirects=True,
            )
            final = urlparse(str(getattr(response, "url", url)))
            final_host = (final.hostname or "").lower()
            final_trusted = any(
                final_host == domain or final_host.endswith("." + domain)
                for domain in trusted_domains
            )
            if not response.ok or final.scheme != "https" or not final_trusted:
                print("Evidence link could not be confirmed live; retaining curated citation:", url)
        except requests.RequestException as exc:
            print("Evidence link check temporarily unavailable; retaining curated citation:",
                  url, str(exc)[:120])

    if len(approved) < 2:
        raise ValueError(
            f"Only {len(approved)} approved institutional sources exist for {topic!r}; "
            "refusing to produce an insufficiently sourced documentary."
        )
    meta["sources"] = approved
    print(f"Evidence check passed for {topic}: {len(approved)} curated institutional sources")
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
        # Try Pixabay first when configured, then fall back to Pexels if it
        # errors or returns no usable clips. One provider's empty result should
        # not prevent the other free provider from being used.
        if pix:
            try:
                r = requests.get("https://pixabay.com/api/videos/",
                                 params={"key": pix, "q": kw[:90], "per_page": 12, "safesearch": "true"},
                                 timeout=30)
                r.raise_for_status()
                for h in r.json().get("hits", []):
                    vs = h.get("videos", {})
                    pick = vs.get("large") if vs.get("large", {}).get("url") else vs.get("medium")
                    if pick and pick.get("url"):
                        found.append((f"px{h['id']}", pick["url"], float(h.get("duration", 7))))
            except Exception as e:
                print("Pixabay footage search failed:", kw, e)
        if not found and pex:
            try:
                orient = "portrait" if fmt == "short" else "landscape"
                r = requests.get("https://api.pexels.com/videos/search",
                                 headers={"Authorization": pex},
                                 params={"query": kw, "orientation": orient, "per_page": 8}, timeout=30)
                r.raise_for_status()
                for v in r.json().get("videos", []):
                    files = [f for f in v.get("video_files", [])
                             if f.get("file_type") == "video/mp4" and f.get("width")]
                    if not files:
                        continue
                    ok = [f for f in files if f["width"] >= W]
                    f = min(ok, key=lambda x: x["width"]) if ok else max(files, key=lambda x: x["width"])
                    found.append((f"pe{v['id']}", f["link"], float(v.get("duration", 7))))
            except Exception as e:
                print("Pexels footage search failed:", kw, e)
        # Keep provider relevance order; random shuffling can select unrelated footage.
        per_kw.append(found[:8])
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
    scenes = meta.get("visual_scenes") or []
    if not scenes:
        raise RuntimeError("No narration-matched visual scene plan; refusing generic filler footage.")
    word_counts = [max(1, len(scene["text"].split())) for scene in scenes]
    total_words = sum(word_counts)
    visual_entries = []
    for scene_no, (scene, count) in enumerate(zip(scenes, word_counts), 1):
        scene_duration = duration * count / total_words
        clips = fetch_clips(scene["keywords"], fmt, scene_duration, W, H)
        if not clips:
            raise RuntimeError(
                f"No matching footage found for narration scene {scene_no}: "
                f"{scene['keywords']}. Refusing unrelated filler footage."
            )
        scene_entries, covered, i = [], 0.0, 0
        while covered < scene_duration + 0.2:
            name, clip_duration = clips[i % len(clips)]
            scene_entries.append(f"file '{name}'")
            covered += clip_duration
            i += 1
        scene_list = WORK / f"scene_{scene_no:02}.txt"
        scene_list.write_text("\n".join(scene_entries), encoding="utf-8")
        scene_video = f"scene_{scene_no:02}.mp4"
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", scene_list.name,
             "-t", f"{scene_duration:.2f}", "-c", "copy", scene_video])
        visual_entries.append(f"file '{scene_video}'")
    (WORK / "list.txt").write_text("\n".join(visual_entries), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "list.txt",
         "-t", f"{duration + 0.5:.2f}", "-c", "copy", "visual.mp4"])
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
            "description": f"{meta['description']}\n\n{hashtags(meta, fmt)}\n\nSources:\n" + "\n".join(f"- {s.get('title', 'Source')}: {s.get('url', '')}" for s in meta.get('sources', []) if s.get('url')) + "\n\nAI-narrated investigative documentary.",
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
    g = f"https://graph.facebook.com/{env('META_GRAPH_VERSION', 'v24.0')}"
    source_lines = "\n".join(f"- {s.get('title', 'Source')}: {s.get('url', '')}" for s in meta.get('sources', []) if s.get('url'))
    desc = f"{meta['title']}\n\n{meta['description']}\n\n{hashtags(meta, fmt)}" + (f"\n\nSources:\n{source_lines}" if source_lines else "")
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



def cloudinary_video_url(video):
    """Upload a rendered video to Cloudinary so Instagram can fetch it by public HTTPS URL."""
    cloud = env("CLOUDINARY_CLOUD_NAME")
    api_key = env("CLOUDINARY_API_KEY")
    api_secret = env("CLOUDINARY_API_SECRET")
    if not all((cloud, api_key, api_secret)):
        raise RuntimeError("Instagram requires CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET")
    timestamp = int(time.time())
    params = {"folder": "scary-autopilot", "timestamp": timestamp}
    signed = "&".join(f"{key}={params[key]}" for key in sorted(params)) + api_secret
    signature = hashlib.sha1(signed.encode("utf-8")).hexdigest()
    with open(video, "rb") as stream:
        response = requests.post(
            f"https://api.cloudinary.com/v1_1/{cloud}/video/upload",
            data={**params, "api_key": api_key, "signature": signature},
            files={"file": stream},
            timeout=1800,
        )
    if not response.ok:
        raise RuntimeError(f"Cloudinary video hosting failed {response.status_code}: {response.text[:500]}")
    secure_url = response.json().get("secure_url", "")
    if not secure_url.startswith("https://"):
        raise RuntimeError("Cloudinary did not return a public HTTPS video URL")
    return secure_url


def post_instagram_reel(video, meta, fmt):
    """Publish a Reel to a linked Instagram professional account via Meta Graph API."""
    ig_user_id, token = env("IG_USER_ID"), env("FB_PAGE_TOKEN")
    if not ig_user_id or not token:
        raise RuntimeError("Instagram requires IG_USER_ID and FB_PAGE_TOKEN")
    if fmt != "short":
        raise RuntimeError("Instagram Reels publishing expects the vertical short video format")
    video_url = cloudinary_video_url(video)
    graph = f"https://graph.facebook.com/{env('META_GRAPH_VERSION', 'v24.0')}"
    source_lines = "\n".join(
        f"- {item.get('title', 'Source')}: {item.get('url', '')}"
        for item in meta.get("sources", []) if item.get("url")
    )
    caption = f"{meta['title']}\n\n{meta['description']}\n\n{hashtags(meta, fmt)}"
    if source_lines:
        caption += f"\n\nSources:\n{source_lines}"
    caption = caption[:2200]

    created = _fb_check(requests.post(
        f"{graph}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": token,
        },
        timeout=180,
    ))
    container_id = created.get("id")
    if not container_id:
        raise RuntimeError("Instagram did not return a Reel container ID")

    # Meta processes the hosted video asynchronously. Publish only after FINISHED.
    for attempt in range(36):
        status = _fb_check(requests.get(
            f"{graph}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=60,
        ))
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram Reel processing {code}: {status.get('status', '')}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram Reel processing did not finish within six minutes")

    published = _fb_check(requests.post(
        f"{graph}/{ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=180,
    ))
    media_id = published.get("id")
    if not media_id:
        raise RuntimeError("Instagram did not return a published media ID")
    return media_id


def post_tiktok_inbox(video, meta):
    """Upload a video to the creator's TikTok inbox; the creator completes publishing in TikTok.

    TikTok's video.upload scope is used intentionally: unattended direct publishing
    requires video.publish approval and an explicit creator-consent/export flow.
    """
    token = env("TIKTOK_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("TIKTOK_ACCESS_TOKEN is not configured")
    size = os.path.getsize(video)
    if size <= 0:
        raise RuntimeError("TikTok upload file is empty")
    # TikTok requires a single whole-file upload below 5 MB. For larger
    # files, distribute bytes evenly across chunks (5–64 MB each).
    if size <= 64 * 1024 * 1024:
        chunks = 1
        chunk_size = size
    else:
        chunks = (size + (10 * 1024 * 1024) - 1) // (10 * 1024 * 1024)
        chunk_size = (size + chunks - 1) // chunks
    endpoint = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    init = requests.post(endpoint, headers=headers, json={"source_info": {
        "source": "FILE_UPLOAD", "video_size": size,
        "chunk_size": chunk_size, "total_chunk_count": chunks,
    }}, timeout=60)
    if not init.ok:
        raise RuntimeError(f"TikTok init failed {init.status_code}: {init.text[:500]}")
    payload = init.json()
    err = payload.get("error", {})
    if err.get("code") not in (None, "", "ok"):
        raise RuntimeError(f"TikTok init rejected: {err.get('code')} {err.get('message', '')}")
    data = payload.get("data", {})
    upload_url, publish_id = data.get("upload_url"), data.get("publish_id")
    if not upload_url or not publish_id:
        raise RuntimeError("TikTok did not return upload_url and publish_id")
    with open(video, "rb") as stream:
        for index in range(chunks):
            start = index * chunk_size
            block = stream.read(chunk_size)
            end = start + len(block) - 1
            upload_headers = {
                "Content-Type": "video/mp4",
                "Content-Length": str(len(block)),
                "Content-Range": f"bytes {start}-{end}/{size}",
            }
            response = requests.put(upload_url, headers=upload_headers, data=block, timeout=900)
            if response.status_code not in (200, 201, 206):
                raise RuntimeError(f"TikTok chunk {index + 1}/{chunks} failed "
                                   f"{response.status_code}: {response.text[:400]}")
    return publish_id


def verify_youtube_upload(video_id):
    """Read the uploaded video back from YouTube and confirm its actual privacy status."""
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=yt_credentials(), cache_discovery=False)
    items = yt.videos().list(part="status,snippet", id=video_id).execute().get("items", [])
    if not items or items[0].get("id") != video_id:
        raise RuntimeError("YouTube upload ID could not be independently read back.")
    privacy = items[0].get("status", {}).get("privacyStatus")
    if privacy != YT_PRIVACY:
        raise RuntimeError(
            f"YouTube privacy verification mismatch: expected {YT_PRIVACY!r}, got {privacy!r}."
        )
    return {"privacy_status": privacy, "title": items[0].get("snippet", {}).get("title", "")}


def verify_facebook_reel(video_id):
    """Read the Page video object back after the Reel publish operation."""
    token = env("FB_PAGE_TOKEN")
    graph = f"https://graph.facebook.com/{env('META_GRAPH_VERSION', 'v24.0')}"
    data = _fb_check(requests.get(
        f"{graph}/{video_id}",
        params={"fields": "id,permalink_url", "access_token": token},
        timeout=60,
    ))
    if str(data.get("id", "")) != str(video_id):
        raise RuntimeError("Facebook Reel ID could not be independently verified.")
    return {"permalink": data.get("permalink_url", "")}


def verify_instagram_reel(media_id):
    """Read the published Instagram media object back and confirm its video/Reel identity."""
    token = env("FB_PAGE_TOKEN")
    graph = f"https://graph.facebook.com/{env('META_GRAPH_VERSION', 'v24.0')}"
    data = _fb_check(requests.get(
        f"{graph}/{media_id}",
        params={
            "fields": "id,media_type,media_product_type,permalink,timestamp",
            "access_token": token,
        },
        timeout=60,
    ))
    if str(data.get("id", "")) != str(media_id):
        raise RuntimeError("Instagram media ID could not be independently verified.")
    if data.get("media_type") not in ("VIDEO", "REELS"):
        raise RuntimeError(
            f"Instagram media is not a video/Reel: {data.get('media_type')!r}."
        )
    product_type = data.get("media_product_type")
    if product_type and product_type != "REELS":
        raise RuntimeError(
            f"Instagram media product type is not REELS: {product_type!r}."
        )
    return {
        "media_type": data.get("media_type"),
        "media_product_type": product_type or "not returned by API",
        "permalink": data.get("permalink", ""),
    }


# TikTok inbox upload uses video.upload; the creator must finish publishing in TikTok.


# ---------------------------------------------------------------- 6. report
def daily_report(hist):
    posts_today = [p for p in hist["posts"] if p["time"][:10] == TODAY]
    s = sum(1 for p in posts_today if p["format"] == "short")
    youtube_count = sum(1 for p in posts_today if p.get("youtube_verified"))
    facebook_count = sum(1 for p in posts_today if p.get("facebook_verified"))
    instagram_count = sum(1 for p in posts_today if p.get("instagram_verified"))
    tiktok_count = sum(1 for p in posts_today if p.get("tiktok_inbox_id"))
    runs_today = [r for r in hist.get("runs", []) if str(r.get("time", "")).startswith(TODAY)]
    failed_statuses = {
        "generation_failed", "preflight_failed", "workflow_failed_before_generation",
        "workflow_failed_during_generation", "workflow_failed_during_delivery",
        "workflow_completed_without_generation_record", "workflow_completed_without_terminal_status",
        "workflow_ended_without_generation_record",
    }
    cancelled_statuses = {
        "workflow_cancelled_before_generation", "workflow_cancelled_during_generation",
        "workflow_cancelled_during_delivery",
    }
    failed_runs = sum(1 for r in runs_today if r.get("status") in failed_statuses)
    cancelled_runs = sum(1 for r in runs_today if r.get("status") in cancelled_statuses)
    lines = [
        f"📊 Daily report {TODAY}",
        f"Scheduled attempts recorded: {len(runs_today)}; failures: {failed_runs}; "
        f"cancelled/missed: {cancelled_runs}",
        f"Videos generated: {len(posts_today)} ({s} short, {len(posts_today) - s} long)",
        f"Platform deliveries: YouTube {youtube_count}; Facebook {facebook_count}; "
        f"Instagram {instagram_count}; TikTok inbox {tiktok_count}",
        "TikTok inbox deliveries are drafts awaiting creator publishing.",
    ]

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
            g = f"https://graph.facebook.com/{env('META_GRAPH_VERSION', 'v24.0')}"
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

    if env("IG_USER_ID") and env("FB_PAGE_TOKEN") and publishing_enabled("ENABLE_INSTAGRAM_PUBLISH"):
        lines.append("\n📸 Instagram: Reels publishing configured")
    else:
        lines.append("\n📸 Instagram: not connected or publishing switch is off")

    if env("TIKTOK_ACCESS_TOKEN") and publishing_enabled("ENABLE_TIKTOK_UPLOAD"):
        lines.append("\n🎵 TikTok: inbox upload configured (creator completes publishing in the app)")
    else:
        lines.append("\n🎵 TikTok: not connected or upload switch is off")
    notify("\n".join(lines))


# ---------------------------------------------------------------- main
def pick_format():
    forced = env("FORCE_FORMAT").lower()
    if forced in ("short", "long"):
        return forced
    # Every 3-hour run produces a vertical short so all four destinations can receive it.
    return "short"


def main():
    hist = load_history()
    if env("REPORT_ONLY") == "true":
        daily_report(hist)
        return

    fmt = pick_format()
    topic = choose_topic(hist)
    run_record = {
        "time": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        **github_run_context(),
        "format": fmt,
        "topic": topic,
        "status": "started",
        "generated": False,
        "platforms": {},
    }
    hist.setdefault("runs", []).append(run_record)
    save_history(hist)

    stage = "audience research"
    try:
        try:
            patterns = research(fmt, hist)
        except Exception as e:
            print("Research failed:", e)
            patterns = "(audience research unavailable; use established evidence, primary sources, balanced uncertainty, and an investigative documentary structure; do not invent events or claims)"

        stage = "script and evidence validation"
        meta = write_script(fmt, patterns, hist, topic=topic, include_visual_plan=False)

        stage = "scene planning"
        meta["visual_scenes"] = make_visual_plan(meta["narration"], topic=topic)
        run_record.update({
            "title": meta["title"],
            "source_count": len(meta.get("sources", [])),
            "visual_scene_count": len(meta.get("visual_scenes", [])),
        })
        save_history(hist)

        stage = "narration and captions"
        duration = make_voice_and_captions(fmt, meta["narration"])

        stage = "scene footage and rendering"
        video = build_video(fmt, meta, duration)
        run_record.update({
            "generated": True,
            "status": "generated",
            "video_file": video.name,
            "duration_seconds": round(duration, 2),
        })
        save_history(hist)
    except Exception as exc:
        run_record.update({
            "status": "generation_failed",
            "failed_stage": stage,
            "error": str(exc)[:900],
        })
        save_history(hist)
        notify(f"❌ Video creation failed ({fmt}) at {stage}:\n{traceback.format_exc()[-1500:]}")
        raise SystemExit(1)

    record = {
        "time": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "format": fmt,
        "title": meta["title"],
        "topic": meta["topic"],
    }
    msgs = []

    def platform_result(name, status, **details):
        run_record["platforms"][name] = {"status": status, **details}
        save_history(hist)

    yt_today = sum(1 for p in hist["posts"] if p.get("youtube_id") and p["time"][:10] == TODAY)
    if not publishing_enabled("ENABLE_YOUTUBE_UPLOAD"):
        platform_result("youtube", "skipped", reason="upload switch is off")
        msgs.append("▶️ YouTube skipped: upload switch is off")
    elif not all(env(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        platform_result("youtube", "blocked", reason="YouTube OAuth credentials are incomplete")
        msgs.append("▶️ YouTube blocked: OAuth credentials are incomplete")
    elif yt_today >= YT_DAILY_CAP:
        platform_result("youtube", "skipped", reason="daily upload cap reached")
        msgs.append("▶️ YouTube skipped: daily upload cap reached")
    else:
        try:
            video_id = post_youtube(video, meta, fmt)
            record["youtube_id"] = video_id
            try:
                verified = verify_youtube_upload(video_id)
                record["youtube_verified"] = True
                record["youtube_privacy"] = verified["privacy_status"]
                platform_result(
                    "youtube", "verified_upload", id=video_id,
                    privacy_status=verified["privacy_status"],
                )
                msgs.append(f"▶️ YouTube verified ({verified['privacy_status']}): https://youtu.be/{video_id}")
            except Exception as verify_error:
                platform_result("youtube", "uploaded_unverified", id=video_id,
                                error=str(verify_error)[:400])
                msgs.append(f"▶️ YouTube upload returned ID {video_id}, but read-back verification failed")
        except Exception as e:
            platform_result("youtube", "failed", error=str(e)[:500])
            notify(f"❌ YouTube upload failed: {str(e)[:700]}")

    if not publishing_enabled("ENABLE_FACEBOOK_PUBLISH"):
        platform_result("facebook", "skipped", reason="publishing switch is off")
        msgs.append("📘 Facebook skipped: publishing switch is off")
    elif not all(env(k) for k in ("FB_PAGE_ID", "FB_PAGE_TOKEN")):
        platform_result("facebook", "blocked", reason="Page ID or Page token is missing")
        msgs.append("📘 Facebook blocked: Page credentials are incomplete")
    else:
        try:
            video_id = post_facebook(video, meta, fmt)
            record["facebook_id"] = video_id
            try:
                verified = verify_facebook_reel(video_id)
                record["facebook_verified"] = True
                record["facebook_permalink"] = verified.get("permalink", "")
                platform_result("facebook", "verified_publish", id=video_id,
                                permalink=verified.get("permalink", ""))
                msgs.append(f"📘 Facebook Reel verified ({video_id})")
            except Exception as verify_error:
                platform_result("facebook", "published_unverified", id=video_id,
                                error=str(verify_error)[:400])
                msgs.append(f"📘 Facebook returned ID {video_id}, but read-back verification failed")
        except Exception as e:
            platform_result("facebook", "failed", error=str(e)[:500])
            notify(f"❌ Facebook post failed: {str(e)[:700]}")

    if not publishing_enabled("ENABLE_INSTAGRAM_PUBLISH"):
        platform_result("instagram", "skipped", reason="publishing switch is off")
        msgs.append("📸 Instagram skipped: publishing switch is off")
    elif fmt != "short":
        platform_result("instagram", "skipped", reason="Reels require the vertical short format")
        msgs.append("📸 Instagram skipped: Reels require the vertical short format")
    elif not all(env(k) for k in (
        "IG_USER_ID", "FB_PAGE_TOKEN", "CLOUDINARY_CLOUD_NAME",
        "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
    )):
        platform_result("instagram", "blocked", reason="Meta or Cloudinary configuration is incomplete")
        msgs.append("📸 Instagram blocked: Meta or Cloudinary configuration is incomplete")
    else:
        try:
            media_id = post_instagram_reel(video, meta, fmt)
            record["instagram_id"] = media_id
            try:
                verified = verify_instagram_reel(media_id)
                record["instagram_verified"] = True
                record["instagram_permalink"] = verified.get("permalink", "")
                platform_result(
                    "instagram", "verified_publish", id=media_id,
                    media_type=verified.get("media_type"),
                    media_product_type=verified.get("media_product_type"),
                    permalink=verified.get("permalink", ""),
                )
                msgs.append(f"📸 Instagram Reel verified ({media_id})")
            except Exception as verify_error:
                platform_result("instagram", "published_unverified", id=media_id,
                                error=str(verify_error)[:400])
                msgs.append(f"📸 Instagram returned ID {media_id}, but read-back verification failed")
        except Exception as e:
            platform_result("instagram", "failed", error=str(e)[:500])
            notify(f"❌ Instagram Reel publish failed: {str(e)[:700]}")

    if not publishing_enabled("ENABLE_TIKTOK_UPLOAD"):
        platform_result("tiktok", "skipped", reason="inbox upload switch is off")
        msgs.append("🎵 TikTok skipped: inbox upload switch is off")
    elif fmt != "short":
        platform_result("tiktok", "skipped", reason="only vertical short videos are sent to the inbox")
        msgs.append("🎵 TikTok skipped: only short-format videos are sent to the inbox")
    elif not env("TIKTOK_ACCESS_TOKEN"):
        platform_result("tiktok", "blocked", reason="TikTok access token is missing")
        msgs.append("🎵 TikTok blocked: access token is missing")
    else:
        try:
            publish_id = post_tiktok_inbox(video, meta)
            record["tiktok_inbox_id"] = publish_id
            platform_result(
                "tiktok", "inbox_uploaded", id=publish_id,
                note="Draft delivered to the TikTok inbox; creator must review and publish.",
            )
            msgs.append("🎵 TikTok inbox upload confirmed; creator must finish publishing in the app")
        except Exception as e:
            platform_result("tiktok", "failed", error=str(e)[:500])
            notify(f"❌ TikTok inbox upload failed: {str(e)[:700]}")

    hist["posts"].append(record)
    run_record["status"] = delivery_completion_status(run_record["platforms"])
    run_record["completed_at"] = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    save_history(hist)
    notify(f"✅ New {fmt} documentary: {meta['title']}\n" + "\n".join(msgs))

    if NOW.hour == REPORT_HOUR:
        daily_report(hist)


if __name__ == "__main__":
    main()