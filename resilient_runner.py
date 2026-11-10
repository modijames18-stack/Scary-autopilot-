"""Resilient entry point for Scary Autopilot.

Uses the existing production pipeline, but provides a local story-writing fallback
when Gemini/Claude is unavailable or over quota. No API key is required for the
fallback. Video rendering and Edge TTS still need the runner's normal dependencies
and network access. Publishing still requires valid platform credentials.
"""
import json
import random
import re

import autopilot as app


def _local_ai(system, prompt, max_tokens=4000, json_mode=False):
    """Never invent an unsourced replacement when the configured AI service fails."""
    raise RuntimeError(
        "AI writing service is unavailable. No documentary was generated because the "
        "offline fallback cannot research and verify the claims and source links required "
        "by the channel's editorial standard."
    )


def _local_research(fmt, hist):
    return (
        "Audience research is unavailable. Use only claims supported by the source entries "
        "included in the script; clearly label FACT, FORECAST and WHAT-IF; do not invent "
        "events, statistics, quotations or source URLs."
    )


def _local_ai(system, prompt, max_tokens=4000, json_mode=False):
    # write_script and its optional polish pass both request the same JSON shape.
    if "Reply with ONLY a JSON object" in prompt or "Improve this short documentary script" in prompt:
        fmt = "short" if "SHORT vertical explainer" in prompt or "short documentary script" in prompt else "long"
        return json.dumps(_make_story(fmt), ensure_ascii=False)
    return "Use a gripping question, explain one future risk with evidence and uncertainty, show human impacts, and end with practical solutions."


def _local_research(fmt, hist):
    return (
        "Local fallback: use an immediate curiosity hook, a specific unsettling setting, "
        "short spoken sentences, escalating clues, atmospheric visuals, and a final reveal. "
        "Create an original plot; do not imitate existing videos."
    )


# Prefer the configured AI provider. If it times out, is over quota, or is
# unavailable, fall back to local original-story generation so a run can continue.
_network_ai = app.ask_ai
_network_research = app.research

def _resilient_ai(system, prompt, max_tokens=4000, json_mode=False):
    try:
        return _network_ai(system, prompt, max_tokens=max_tokens, json_mode=json_mode)
    except Exception as exc:
        print("AI provider unavailable; refusing to generate an unsourced documentary:", str(exc)[:300])
        raise RuntimeError("Configured AI provider unavailable; safe documentary generation stopped.") from exc

def _resilient_research(fmt, hist):
    try:
        return _network_research(fmt, hist)
    except Exception as exc:
        print("Research unavailable; using local guidance:", str(exc)[:300])
        return _local_research(fmt, hist)

app.ask_ai = _resilient_ai
app.research = _resilient_research

if __name__ == "__main__":
    app.main()
