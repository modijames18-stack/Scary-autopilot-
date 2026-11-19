"""Persist scheduled GitHub runs that stop before the autopilot can record them."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


HISTORY_FILE = Path(__file__).resolve().with_name("history.json")

# Workflow step outcomes let the history explain where a scheduled attempt stopped,
# even when the autopilot never started and could not write its own run record.
STEP_FAILURES = (
    ("MEDIA_TOOLS_OUTCOME", "runner media-tool installation",
     "FFmpeg/font setup failed before video generation."),
    ("PYTHON_PACKAGES_OUTCOME", "Python dependency installation",
     "Python package installation failed before validation."),
    ("PYTHON_SYNTAX_OUTCOME", "Python syntax validation",
     "Python syntax validation failed before generation."),
    ("UNIT_TESTS_OUTCOME", "automated unit tests",
     "Automated unit tests failed before generation."),
    ("PREFLIGHT_OUTCOME", "platform configuration preflight",
     "Platform configuration preflight failed before generation."),
    ("AUTOPILOT_OUTCOME", "autopilot generation or delivery",
     "The autopilot generation or delivery step failed."),
)


def workflow_failure_details(environ):
    """Return the first failed/cancelled workflow stage without exposing environment values."""
    for variable, stage, message in STEP_FAILURES:
        outcome = str(environ.get(variable, "")).strip().lower()
        if outcome in ("failure", "cancelled"):
            return stage, message
    return (
        "workflow setup or preflight",
        "The scheduled workflow ended before the autopilot created a generation record.",
    )


def record_workflow_outcome(environ=None, history_file=None):
    """Record missed scheduled runs and terminalize interrupted run records without secrets."""
    e = os.environ if environ is None else environ
    if str(e.get("GITHUB_EVENT_NAME", "")).strip() != "schedule":
        return False

    run_id = str(e.get("GITHUB_RUN_ID", "")).strip()
    if not run_id:
        return False
    attempt = str(e.get("GITHUB_RUN_ATTEMPT", "1")).strip() or "1"
    job_status = str(e.get("JOB_STATUS", "unknown")).strip().lower()
    path = Path(history_file) if history_file else HISTORY_FILE

    if path.exists():
        history = json.loads(path.read_text(encoding="utf-8"))
    else:
        history = {}
    history.setdefault("posts", [])
    history.setdefault("patterns", {})
    history.setdefault("runs", [])

    existing = next(
        (
            item for item in history["runs"]
            if str(item.get("github_run_id") or item.get("run_id") or "") == run_id
            and str(item.get("github_run_attempt") or item.get("run_attempt") or "1") == attempt
        ),
        None,
    )

    if existing is not None:
        current = str(existing.get("status", ""))
        if current in ("started", "generated"):
            if job_status == "cancelled":
                existing["status"] = (
                    "workflow_cancelled_during_generation"
                    if current == "started"
                    else "workflow_cancelled_during_delivery"
                )
            elif job_status == "failure":
                existing["status"] = (
                    "workflow_failed_during_generation"
                    if current == "started"
                    else "workflow_failed_during_delivery"
                )
            elif job_status == "success":
                existing["status"] = "workflow_completed_without_terminal_status"
            else:
                return False
            detected_stage, detected_error = workflow_failure_details(e)
            existing["failed_stage"] = existing.get("failed_stage") or detected_stage
            existing["error"] = (
                detected_error if job_status in ("failure", "cancelled")
                else "GitHub Actions completed before the autopilot persisted a terminal run status."
            )
            existing["workflow_status"] = job_status
            existing["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            history["runs"] = history["runs"][-500:]
            path.write_text(json.dumps(history, indent=2), encoding="utf-8")
            print("Updated interrupted scheduled run history:", run_id, existing["status"])
            return True
        return False

    if job_status == "cancelled":
        status = "workflow_cancelled_before_generation"
        failed_stage, error = workflow_failure_details(e)
    elif job_status == "failure":
        status = "workflow_failed_before_generation"
        failed_stage, error = workflow_failure_details(e)
    elif job_status == "success":
        status = "workflow_completed_without_generation_record"
        failed_stage = "generation record"
        error = "The workflow completed without creating a generation record."
    else:
        status = "workflow_ended_without_generation_record"
        failed_stage, error = workflow_failure_details(e)

    history["runs"].append({
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "github_run_id": run_id,
        "github_run_number": str(e.get("GITHUB_RUN_NUMBER", "")).strip() or None,
        "github_run_attempt": attempt,
        "github_event": "schedule",
        "format": "short",
        "status": status,
        "generated": False,
        "workflow_status": job_status,
        "failed_stage": failed_stage,
        "error": error,
        "platforms": {},
    })
    history["posts"] = history["posts"][-500:]
    history["runs"] = history["runs"][-500:]
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print("Recorded scheduled workflow outcome:", run_id, status, failed_stage)
    return True


if __name__ == "__main__":
    record_workflow_outcome()
