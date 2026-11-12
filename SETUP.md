# Scary Autopilot — four-platform publishing

The scheduled workflow runs every three hours (eight runs per day). Each scheduled run creates one original vertical short documentary and attempts delivery to all four connected destinations: YouTube Shorts, Facebook Reels, Instagram Reels, and TikTok inbox.

## Required account connections

Add credentials in GitHub → repository → **Settings → Secrets and variables → Actions → Secrets**. Never paste tokens into chat or commit them into the repository.

| Secret | Used for |
|---|---|
| `GEMINI_API_KEY` | Scriptwriting and documentary scene planning |
| `PIXABAY_API_KEY` or `PEXELS_API_KEY` | Real documentary stock footage |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | YouTube upload |
| `FB_PAGE_ID`, `FB_PAGE_TOKEN` | Facebook Page Reels |
| `IG_USER_ID` | Instagram professional account ID |
| `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` | Securely host the generated video at a public HTTPS URL for Instagram's media fetch |
| `TIKTOK_ACCESS_TOKEN` | TikTok Content Posting API inbox upload (`video.upload` scope) |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional run alerts |

## AI reliability settings

Gemini uses `gemini-3.8-flash` by default and automatically tries `gemini-3.6-flash` after bounded transient failures. Both paths still pass through the same evidence and documentary-quality checks; a failed provider never triggers an invented fallback script.

Optional GitHub Actions repository **Variables** (not Secrets):

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_MODEL` | `gemini-3.8-flash` | Primary Gemini model |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.6-flash` | Comma-separated fallback models |
| `GEMINI_TIMEOUT_SECONDS` | `75` | Per-request timeout, bounded by the application |
| `GEMINI_ATTEMPTS_PER_MODEL` | `2` | Attempts per model, bounded by the application |

The workflow records scheduled slots that stop before generation and marks interrupted runs in history. Topic rotation advances after each attempted episode, including failed attempts, so a repeated provider outage does not lock the channel onto one topic.

Instagram publishing requires an Instagram **Professional** (Creator or Business) account, the required Meta app permissions, and an account linked to a Facebook Page. The Page access token must include the relevant Instagram publishing and Page permissions. Cloudinary is used because Instagram's publishing API must fetch the video from a publicly accessible HTTPS URL. A Cloudinary account and API credentials are required.

## Enable publishing

Under **Settings → Secrets and variables → Actions → Variables**, add:

| Variable | Value |
|---|---|
| `ENABLE_YOUTUBE_UPLOAD` | `true` after YouTube OAuth is authorized |
| `ENABLE_FACEBOOK_PUBLISH` | `true` after Page publishing permission is granted |
| `ENABLE_INSTAGRAM_PUBLISH` | `true` after Instagram/Meta permissions and Cloudinary are ready |
| `ENABLE_TIKTOK_UPLOAD` | `true` after TikTok OAuth is authorized |
| `YOUTUBE_PRIVACY` | Keep `private` for the first test; change only after reviewing the result |
| `YOUTUBE_DAILY_UPLOADS` | `8` target (subject to the channel/API account's actual limits) |
| `META_GRAPH_VERSION` | Optional; defaults to `v24.0` |
| `TTS_VOICE` | Optional; defaults to `en-US-ChristopherNeural` |

The workflow's preflight checks every enabled platform before video generation. It reports missing secret names only and never prints secret values. Do not turn on a platform until its credentials are saved and tested.

## Important TikTok limitation

The current TikTok integration uploads each short video to the account's TikTok inbox using the official `video.upload` scope. The creator must open the TikTok notification, review the draft, and tap to publish. This is not unattended public posting.

TikTok's `video.publish` Direct Post requires approved app access, user authorization, creator information checks, and an explicit creator-consent/export flow. Unaudited apps are restricted to private visibility. The scheduled workflow does not bypass those requirements. The inbox upload means TikTok receives the video every three hours, but a person still completes public posting.

Official docs: [TikTok Direct Post](https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post), [TikTok Upload](https://developers.tiktok.com/docs/en/content-posting-api-reference-upload-video).

## How the video pipeline works

1. Select the next topic from a deliberate, non-random evidence-backed rotation. Environmental investigations are intentionally frequent: water scarcity and drying rivers, climate and extreme weather, ocean warming and glacier loss, air pollution, and river ecosystems. The rotation also covers AI and jobs, energy, power grids, and internet infrastructure.
2. Write a short investigative script grounded in approved institutional sources.
3. Label documented facts, credible forecasts, and hypothetical scenarios clearly.
4. Create narration and captions, then build a vertical video using scene-by-scene documentary footage searches.
5. Refuse generic filler footage when a scene has no relevant footage.
6. Attempt publishing to each enabled platform and record each platform's own returned post/upload ID.
7. Send a run report and save the video artifact/history.

The default scheduled format is a short vertical documentary so the same video can be delivered to all four destinations on every three-hour run. A manual workflow dispatch can still force a long video for a separate YouTube/Facebook test.

## First live test

1. Save the required credentials in GitHub Actions Secrets.
2. Enable the platform variables only after each account's OAuth/app permissions are granted.
3. Keep YouTube privacy set to `private`.
4. Open **Actions → Autopilot → Run workflow** and start one test run.
5. Review the generated MP4 and check the run log for a confirmed result from each platform.
6. Do not treat an uploaded TikTok inbox draft as a public post.

A successful code test does not mean that accounts are connected: live connection is confirmed only after the platform returns a successful upload/publish ID. Public posting and monetization remain subject to each platform's app review, account eligibility, quotas, and policies.

## Editorial standard

Every episode must be a credible, solution-focused investigative documentary—not random horror fiction. Use verifiable evidence, realistic footage matched to the narration, clear uncertainty, strong narration, careful pacing, and practical solutions. Never invent statistics, reports, quotations, eyewitnesses, emergencies, or source URLs. Treat a worldwide blackout or one-world-government scenario as hypothetical unless real evidence supports a narrower claim. Environmental topics must reflect actual conditions and credible forecasts, not sensational claims.
