"""Safe entry point for Scary Autopilot.

Use the configured AI research and writing provider only. If it is unavailable,
stop the run rather than creating an unsourced or fictional replacement story.
"""
import autopilot as app


def _resilient_ai(system, prompt, max_tokens=4000, json_mode=False):
    try:
        return _network_ai(system, prompt, max_tokens=max_tokens, json_mode=json_mode)
    except Exception as exc:
        print("AI provider unavailable; refusing to generate an unsourced documentary:",
              str(exc)[:300])
        raise RuntimeError(
            "Configured AI provider unavailable; safe documentary generation stopped."
        ) from exc


_network_ai = app.ask_ai
app.ask_ai = _resilient_ai

if __name__ == "__main__":
    app.main()
