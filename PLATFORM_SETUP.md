# Platform connection and publishing status

This document describes the integrations currently present in the code and the account-side approvals still required. Never put tokens or passwords in source files, issue comments, or chat. Store credentials only as encrypted GitHub Actions secrets.

## Implemented integrations

| Destination | Code implemented | Actual delivery behavior | Owner-side requirements |
| --- | --- | --- | --- |
| YouTube Shorts | Yes | Resumable upload; visibility defaults to **private** | OAuth client ID, client secret, refresh token, YouTube API access |
| Facebook Reels/Page | Yes | Uploads a Reel for short-format episodes | Page ID and Page access token with approved publishing permissions |
| Instagram Reels | Yes | Uploads the video to Cloudinary, creates a Reel container, waits for processing, then publishes | Professional Instagram account linked to a Facebook Page; Meta app permissions; Instagram account ID; Page token; Cloudinary credentials |
| TikTok | Yes, inbox upload only | Uploads a draft to the creator's TikTok inbox using `video.upload`; the creator must review and finish publishing in TikTok | TikTok developer app, OAuth authorization, approved `video.upload` scope and access token |

A successful code test is not proof that a social account is connected. A live connection is confirmed only when the platform accepts an upload/publish request and returns its media or upload ID. TikTok inbox delivery is not a public post.

## Documentary research and evidence

The script writer uses a curated evidence catalogue for AI and jobs, AI governance, water scarcity, power-grid resilience, internet infrastructure, climate and food security, ocean warming, air pollution, and river ecosystem health. The selected topic determines which curated institutional sources are attached to the episode. Model-supplied source URLs are not trusted: the verifier replaces them with the catalogue's approved sources.

The verifier requires at least two curated HTTPS sources from approved institutional domains. Live website reachability is logged as diagnostic information, not used as a hard gate, because public institutions can rate-limit automated requests. This does not mean every narration sentence has been independently fact-checked; the script must remain within the supplied evidence summaries and distinguish documented facts, credible forecasts, and hypothetical scenarios.

YouTube OAuth is optional for audience-interest research. Without a YouTube refresh token, popularity research is skipped and the project continues from the curated evidence catalogue. Popular videos are never treated as factual evidence.

## Publishing switches

The scheduled workflow runs every three hours. Publishing remains opt-in: credentials alone do not enable a platform. Add these GitHub Actions **Variables** only after reviewing the generated videos and authorizing the relevant destination:

- `ENABLE_YOUTUBE_UPLOAD=true`
- `ENABLE_FACEBOOK_PUBLISH=true`
- `ENABLE_INSTAGRAM_PUBLISH=true`
- `ENABLE_TIKTOK_UPLOAD=true`

If a switch is missing, blank, or anything other than `true`, that destination is skipped. The preflight step checks that enabled destinations have their required secrets before generation starts.

YouTube visibility defaults to `private`. Keep it private for initial testing. Public visibility is a separate account-owner decision and remains subject to YouTube policy, app verification, quotas, and channel eligibility.

## Required GitHub Actions secrets

### AI writing and stock footage
- `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` (choose the provider with optional `AI_PROVIDER` variable: `gemini` or `anthropic`)
- At least one of `PIXABAY_API_KEY` or `PEXELS_API_KEY`

### YouTube
- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

### Facebook and Instagram
- `FB_PAGE_ID`
- `FB_PAGE_TOKEN`
- `IG_USER_ID`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`

Instagram requires a Professional (Creator or Business) account linked to a Facebook Page, and a Meta app/token with the permissions required by the current Instagram Graph API publishing flow. The app uploads the rendered video to Cloudinary to obtain a public HTTPS media URL, creates a Reel container, waits for Meta to report that processing is finished, and then publishes it. Cloudinary is therefore required by the current implementation.

### TikTok
- `TIKTOK_ACCESS_TOKEN`

The current implementation uses TikTok's official inbox-upload flow (`video.upload`). The video is delivered to the creator's TikTok inbox, but the creator must open the notification, review the draft, and complete the public post in TikTok. Do not describe this as unattended public publishing.

TikTok Direct Post (`video.publish`) is a separate integration with additional app approval, creator-consent, and UX requirements. This repository does not claim to perform unattended public Direct Posts.

### Optional notifications
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Relevant GitHub Actions variables

| Variable | Recommended value / behavior |
| --- | --- |
| `ENABLE_YOUTUBE_UPLOAD` | `true` only after OAuth is authorized and private test upload is reviewed |
| `ENABLE_FACEBOOK_PUBLISH` | `true` only after Page publishing permissions are granted |
| `ENABLE_INSTAGRAM_PUBLISH` | `true` only after Meta permissions, linked account, and Cloudinary are ready |
| `ENABLE_TIKTOK_UPLOAD` | `true` only after TikTok OAuth and inbox-upload scope are authorized |
| `YOUTUBE_PRIVACY` | `private` for initial tests; default is private |
| `YOUTUBE_DAILY_UPLOADS` | `8` target uploads/day; actual API/channel limits take precedence |
| `META_GRAPH_VERSION` | Optional; code default is `v24.0` |
| `TTS_VOICE` | Optional; default is `en-US-ChristopherNeural` |

The preflight output reports only whether a setting is present. It never prints secret values.

## Safe testing sequence

1. Run syntax checks and automated unit tests.
2. Generate a video and inspect the MP4 artifact for narration, captions, relevant footage, and factual quality.
3. Test YouTube with private visibility.
4. Test Facebook on a Page the owner administers.
5. Test Instagram Reels with the linked Professional account and Cloudinary-hosted media.
6. Test TikTok inbox upload, then confirm the draft appears in the account's TikTok inbox. Public posting still requires the creator to finish the in-app flow.
7. Enable public visibility or broader publishing only after the owner has reviewed the results and explicitly authorized it.

The workflow creates one vertical short per three-hour run (eight scheduled runs per day). This is a target cadence, not a guarantee: GitHub Actions availability, API quotas, provider limits, and failed jobs can interrupt runs.

No account settings, payout details, monetization settings, or public publishing permissions should be changed without the account owner's explicit approval. Monetization is not guaranteed by automated posting and remains controlled by each platform's eligibility and policy requirements.
