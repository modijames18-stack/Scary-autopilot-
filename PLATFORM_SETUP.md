# Platform connection plan

This document describes what is implemented and what is required before enabling each social platform. Never put tokens or passwords in source files or chat. Add credentials only as encrypted GitHub Actions secrets.

## Current implementation

| Platform | Current code | What is still needed |
| --- | --- | --- |
| YouTube | Upload function and channel/report code exist | OAuth client ID, client secret, refresh token, enabled YouTube APIs, and a successful private test upload |
| Facebook Pages | Page video/Reel publishing function exists | Page ID, Page access token with approved permissions, and a test Page upload |
| Instagram | Not implemented | Professional Instagram account linked to a Facebook Page, Meta app permissions, Instagram account ID, and public HTTPS video hosting |
| TikTok | Not implemented; previous code only skipped it | A compliant TikTok developer app and approved scopes; see restrictions below |

## Documentary research and evidence

The script writer receives a curated evidence catalogue covering AI and jobs, AI governance, water scarcity, power-grid resilience, internet infrastructure, climate and food security, and harmful algal blooms. The selected topic determines which exact source links are attached to the video. The runner checks that at least two approved source links are reachable before producing a documentary.

YouTube OAuth is optional for audience-interest research. If no YouTube refresh token is configured, the workflow skips that optional popularity research and continues using the curated evidence catalogue. Popular videos are never treated as factual evidence.

A reachable source link is not, by itself, proof that every narration sentence is supported. Scripts must stay within the supplied source summaries, label forecasts and hypothetical scenarios, and should be reviewed before public release.

## Publishing safety switches

The scheduled workflow runs every three hours, but social publishing is disabled unless the repository owner explicitly enables it. Add these GitHub Actions **Variables** only after reviewing a generated video and deciding to allow that platform to publish:
- `ENABLE_YOUTUBE_UPLOAD=true` to allow YouTube uploads (the default remains disabled).
- `ENABLE_FACEBOOK_PUBLISH=true` to allow Facebook Page publishing (the default remains disabled).

If either variable is missing, blank, or anything other than `true`, that platform is skipped. Credentials alone never authorize a post. YouTube visibility still defaults to `private`; changing it to `public` is a separate owner decision.

## YouTube

Configure these GitHub Actions secrets:
- `YT_CLIENT_ID`
- `YT_CLIENT_SECRET`
- `YT_REFRESH_TOKEN`

Keep `YOUTUBE_PRIVACY=private` until a private test upload and review succeed. Do not switch to public automatically.

## Facebook Pages

Configure:
- `FB_PAGE_ID`
- `FB_PAGE_TOKEN`

Use a Page token issued through a Meta app with the required Page publishing permissions. Test with a Page you administer. Publishing errors must be surfaced; do not silently mark failed posts as successful.

## Instagram

Instagram publishing is not ready to enable in this repository. The supported publishing flow for Reels requires a Professional account and a media container followed by a publish request. Meta fetches the video from a publicly accessible URL. The current workflow only stores the finished video as a short-lived GitHub Actions artifact, which is not a suitable permanent public media URL.

Before implementation, choose and configure a secure media-hosting destination that provides a public HTTPS URL for each video, then configure the Instagram Professional account, linked Page, app permissions, account ID, and token. Do not publish until the account and media URL have been tested.

## TikTok

Do not add unattended direct posting as a simple background job. TikTok's Content Posting API requires the creator information to be queried, the creator to be shown the posting details, and the creator to explicitly consent to the post. Un-audited apps are restricted to private visibility. TikTok's developer guidelines also say the API is not intended for an internal utility limited to managing accounts belonging to the app operator.

For this project, keep TikTok as a user-confirmed export/share step unless the app is redesigned to meet TikTok's product-use and UX requirements and TikTok approves the app and scopes. Never promise automatic public posting before that approval.

## Safe testing sequence

1. Validate code and scene-planning tests without platform credentials.
2. Test video generation and inspect the finished video artifact.
3. Test YouTube with private visibility.
4. Test Facebook on the owner's Page.
5. Add secure public media hosting and then test Instagram container publishing.
6. Reassess TikTok against current developer approval and UX requirements before implementing any posting workflow.

No account settings, payout details, monetization settings, or public publishing should be changed without the account owner's explicit approval.
