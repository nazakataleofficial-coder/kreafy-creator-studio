# Smart API & Provider Manager — planning specification

## Providers under consideration
Gemini, Higgsfield, ElevenLabs, Azure Speech, OpenAI, fal.ai, Replicate, OpenRouter; local Kokoro, Piper, Whisper, Ollama, FFmpeg.

Subscriptions to ChatGPT, Gemini or Higgsfield consumer websites do NOT automatically grant developer API credits. Availability and pricing must be checked on account/provider basis.

## Secure adapter registry
Provider ID, auth method, base URL, models, capabilities (text/image/video/audio), supported inputs, output types, async status/cancel, quota scope, cost, license/terms, provider reliability and data-handling policy.

## Credential handling
Select provider first; masked key input; OS-protected secret store; backend verification; no key in web bundle, logs, exported projects or Git.

## Model routing
Task → capability requirements → user-approved local/remote model → hardware/cost check → execute → status/error handling. Explicit approval for paid call and fallback, with spend controls.

## Multi-key failover API-011
Support separate authorized credentials and valid independent quota scopes. Google Gemini quotas can be per project (multiple keys in one project share limits). Handle 429 with Retry-After or backoff; distinguish quota exhaustion, transient errors and 401/403. No key cycling as provider limit bypass. Track per model/project health, cooldown, attempts and idempotent outputs.

## Acceptance checks
Valid/invalid key; distinct same-project keys grouped; safe transient retry; forbidden paid fallback without consent; no secret leaks; provider offline; cancel; retry without duplicating completed media.
