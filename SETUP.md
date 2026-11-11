# Scary Autopilot — setup and platform connections

The workflow runs every three hours in GitHub Actions. It creates evidence-led documentary videos, stores a short-lived video artifact, updates `history.json`, and sends optional Telegram alerts.

## 1. Add repository secrets

Open the repository on GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

Add only the credentials for services you actually connect:

| Secret | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini script writing and scene planning (recommended low-cost/free-tier AI option, subject to provider limits) |
| `ANTHROPIC_API_KEY` | Optional Claude alternative |
| `PEXELS_API_KEY` | Documentary footage fallback |
| `PIXABAY_API_KEY` | Primary documentary footage search |
| `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` | YouTube OAuth upload and analytics |
| `FB_PAGE_ID`, `FB_PAGE_TOKEN` | Facebook Page publishing and reporting |
| `TIKTOK_ACCESS_TOKEN` | TikTok Content Posting API user token with `video.upload` permission |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional run alerts |

Never paste tokens into source files, issues, or chat messages. If a token is exposed, revoke and replace it.

## 2. Set repository Actions variables

Open **Settings → Secrets and variables → Actions → Variables** and add:

| Variable | Suggested value | Meaning |
|---|---|---|
| `ENABLE_YOUTUBE_UPLOAD` | `false` | Set to `true` only after YouTube OAuth is tested |
| `ENABLE_FACEBOOK_PUBLISH` | `false` | Set to `true` only after Page permissions are tested |
| `ENABLE_TIKTOK_UPLOAD` | `false` | Set to `true` after TikTok OAuth is configured |
| `YOUTUBE_PRIVACY` | `private` | Keep private until a test upload is reviewed |
| `YOUTUBE_DAILY_UPLOADS` | `2` | Conservative daily upload cap |
| `LONG_HOURS` | `6,18` | UTC hours for long documentaries |
| `TTS_VOICE` | `en-US-ChristopherNeural` | Narration voice |
| `REPORT_HOUR_UTC` | `21` | Daily report hour |

Publishing switches are deliberately off by default. Do not enable a platform until its credentials and account permissions are confirmed.

## 3. TikTok connection — important limitation

The code can upload a short video to the TikTok inbox using the official Content Posting API `video.upload` scope. The creator must then open TikTok notifications, review the video, and complete publishing in the TikTok app.

To connect it:

1. Create or open your app at [TikTok for Developers](https://developers.tiktok.com/).
2. Add the **Content Posting API** product and configure the video-upload permission.
3. Complete TikTok's app review and OAuth authorization for the account you own.
4. Obtain a user access token with the `video.upload` scope.
5. Save it as the GitHub Actions secret `TIKTOK_ACCESS_TOKEN`.
6. Set `ENABLE_TIKTOK_UPLOAD` to `true`.

TikTok direct auto-publishing is not enabled here. Its `video.publish` scope requires approval and a creator-consent/export flow, and unaudited clients are restricted to private visibility. This project does not bypass those requirements. Access tokens expire; if TikTok reports an expired token, re-authorize and replace the secret. The current workflow uploads **short-format videos only** to the inbox.

Official docs: [TikTok Content Posting API — Get Started](https://developers.tiktok.com/docs/en/content-posting-api-get-started), [Upload API](https://developers.tiktok.com/docs/en/content-posting-api-reference-upload-video).

## 4. YouTube and Facebook

- YouTube uses OAuth refresh-token credentials and the YouTube Data API. Start with `YOUTUBE_PRIVACY=private`; review the video before changing to public.
- Facebook requires a Page access token with the relevant Page video publishing permissions. Personal-profile publishing is not supported by this integration.
- Meta and Google may require app review, verification, or account eligibility. A successful code deployment does not grant those permissions.

## 5. Configuration preflight\n\nEvery scheduled run checks that an AI provider and at least one stock-footage provider are configured. If a platform switch is enabled but its required credentials are missing, the run stops before creating a video and reports exactly which credential names are missing (never their values). Platforms left disabled are clearly reported as disabled. This prevents silent skipped publishing.\n\n## 6. Run and review

1. Open the repository's **Actions** tab.
2. Select **Autopilot** → **Run workflow**.
3. Start with `report_only=false` and keep publishing switches off until a generated artifact is reviewed.
4. Open the run and download the `last-video` artifact to inspect the MP4.
5. Check the run logs and Telegram alert for failures.

The scheduled workflow is every three hours. GitHub Actions usage limits and provider quotas still apply.

## 7. Editorial and safety rules

Videos must remain investigative documentaries, not fabricated horror stories. Use the curated evidence catalogue, distinguish documented facts from forecasts and what-if scenarios, disclose AI narration, and refuse to fill missing footage with unrelated clips. Hypothetical global outages or one-world-government scenarios must be identified as hypothetical. Monetization eligibility and revenue are controlled by each platform; this software cannot guarantee approval or earnings.
