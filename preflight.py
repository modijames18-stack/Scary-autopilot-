"""Safe configuration preflight for Scary Autopilot.

Reports only whether required settings are present; never prints secret values.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


HISTORY_FILE = Path(__file__).resolve().with_name("history.json")


def inspect_config(environ=None):
    e = os.environ if environ is None else environ
    checks = []
    errors = []

    def has(*keys):
        return all(str(e.get(k, "")).strip() for k in keys)

    ai_provider = str(e.get("AI_PROVIDER", "")).strip().lower()
    if ai_provider == "anthropic":
        ai_ok = has("ANTHROPIC_API_KEY")
        ai_label = "Anthropic"
    elif ai_provider == "gemini":
        ai_ok = has("GEMINI_API_KEY")
        ai_label = "Gemini"
    elif has("ANTHROPIC_API_KEY"):
        ai_ok, ai_label = True, "Anthropic (automatic selection)"
    else:
        ai_ok, ai_label = has("GEMINI_API_KEY"), "Gemini (automatic selection)"
    checks.append(("AI writing", ai_ok, ai_label))
    if not ai_ok:
        errors.append("Add the API key for the selected AI provider.")

    footage_ok = has("PIXABAY_API_KEY") or has("PEXELS_API_KEY")
    checks.append(("Stock footage", footage_ok, "Pixabay or Pexels"))
    if not footage_ok:
        errors.append("Add at least one footage key: PIXABAY_API_KEY or PEXELS_API_KEY.")

    platforms = [
        ("YouTube", "ENABLE_YOUTUBE_UPLOAD", ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")),
        ("Facebook Page", "ENABLE_FACEBOOK_PUBLISH", ("FB_PAGE_ID", "FB_PAGE_TOKEN")),
        ("Instagram Reels", "ENABLE_INSTAGRAM_PUBLISH", (
            "IG_USER_ID", "FB_PAGE_TOKEN", "CLOUDINARY_CLOUD_NAME",
            "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
        )),
        ("TikTok inbox", "ENABLE_TIKTOK_UPLOAD", ("TIKTOK_ACCESS_TOKEN",)),
    ]
    for label, switch, secrets in platforms:
        enabled = str(e.get(switch, "")).strip().lower() == "true"
        configured = has(*secrets)
        ready = enabled and configured
        state = "ready" if ready else ("disabled" if not enabled else "incomplete")
        checks.append((label, ready, state))
        if enabled and not configured:
            missing = ", ".join(k for k in secrets if not str(e.get(k, "")).strip())
            errors.append(f"{label} is enabled but missing: {missing}.")

    telegram_ok = has("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
    checks.append(("Telegram alerts", telegram_ok, "configured" if telegram_ok else "optional / not configured"))
    return checks, errors


def record_preflight_failure(checks, errors, environ=None):
    """Persist configuration failures without ever copying secret values into history."""
    e = os.environ if environ is None else environ
    try:
        if HISTORY_FILE.exists():
            history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        else:
            history = {}
        history.setdefault("posts", [])
        history.setdefault("patterns", {})
        history.setdefault("runs", [])

        run_id = str(e.get("GITHUB_RUN_ID", "")).strip() or None
        run_attempt = str(e.get("GITHUB_RUN_ATTEMPT", "")).strip() or None
        if run_id and any(
            item.get("run_id") == run_id and item.get("run_attempt") == run_attempt
            for item in history["runs"]
        ):
            return

        platform_names = {"YouTube", "Facebook Page", "Instagram Reels", "TikTok inbox"}
        platforms = {}
        for name, _ok, state in checks:
            if name in platform_names:
                platforms[name] = {
                    "status": (
                        "blocked" if state == "incomplete"
                        else "skipped" if state == "disabled"
                        else "configuration_ready"
                    ),
                    "configuration_state": state,
                }

        history["runs"].append({
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "run_id": run_id,
            "run_attempt": run_attempt,
            "format": str(e.get("FORCE_FORMAT", "")).strip() or "short",
            "status": "preflight_failed",
            "generated": False,
            "failed_stage": "configuration preflight",
            "error": "; ".join(str(error) for error in errors)[:900],
            "checks": [{"name": name, "ready": bool(ok), "state": state}
                       for name, ok, state in checks],
            "platforms": platforms,
        })
        history["posts"] = history["posts"][-500:]
        history["runs"] = history["runs"][-500:]
        HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    except Exception as exc:
        # Preserve the original preflight failure even if history storage is unavailable.
        print("Could not persist preflight failure:", type(exc).__name__)


def main():
    checks, errors = inspect_config()
    print("Scary Autopilot configuration check")
    for name, ok, state in checks:
        print(f"{'OK' if ok else 'INFO'}  {name}: {state}")
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"- {error}")
        record_preflight_failure(checks, errors)
        return 1
    print("Preflight passed. Disabled platforms will not receive posts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
