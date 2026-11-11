"""Safe configuration preflight for Scary Autopilot.

Reports only whether required settings are present; never prints secret values.
"""
import os
import sys


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


def main():
    checks, errors = inspect_config()
    print("Scary Autopilot configuration check")
    for name, ok, state in checks:
        print(f"{'OK' if ok else 'INFO'}  {name}: {state}")
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Preflight passed. Disabled platforms will not receive posts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
